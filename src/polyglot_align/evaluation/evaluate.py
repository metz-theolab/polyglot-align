"""Évaluation d'un alignement contre le gold CATSS nettoyé, par blocs.

Applique DECISIONS.md, « Évaluation par blocs CATSS » : un lien prédit est
juste s'il reste à l'intérieur d'une unité CATSS de type `align` (ou s'il
correspond à un lien reconstruit `{...}`).

Evaluator juge les liens d'un passage (JSONL, format dans alignment.py) contre un Gold,
et écrit le CSV de relecture. measures() calcule les mesures à partir des
comptes bruts (aussi utilisée par experiment.py pour le total).
"""
import csv
from collections import Counter, defaultdict

from polyglot_align.alignment import read_jsonl
from polyglot_align.corpus import Corpus
from polyglot_align.evaluation.gold import Gold


def measures(c: Counter) -> dict:
    """Mesures à partir des comptes bruts (moyenne micro)."""
    div = lambda a, b: round(a / b, 4) if b else None
    p = div(c["justes"], c["justes"] + c["faux"])
    r = div(c["blocs_trouves"], c["blocs_evaluables"])
    f1 = round(2 * p * r / (p + r), 4) if p and r else None
    aer = (1 - (c["aer_AinS"] + c["aer_AinP"]) / (c["aer_A"] + c["aer_S"])
           if c["aer_A"] + c["aer_S"] else None)
    return {
        "precision": p, "rappel_blocs": r, "f1": f1,
        "nonalign_exactitude": div(c["nonalign_respectes"], c["nonalign_tokens"]),
        "aer": round(aer, 4) if aer is not None else None,
        "aer_precision": div(c["aer_AinP"], c["aer_A"]),
        "aer_rappel": div(c["aer_AinS"], c["aer_S"]),
        "couverture_hb": div(c["tokens_hb_rattaches"], c["tokens_hb"]),
        "couverture_gr": div(c["tokens_gr_rattaches"], c["tokens_gr"]),
    }


class Evaluator:
    """Évalue les alignements d'un livre contre son gold."""

    def __init__(self, gold: Gold, he: Corpus, lxx: Corpus, layer: str = "w"):
        self.gold, self.he, self.lxx = gold, he, lxx
        # tokens rattachés au gold : ceux de la couche alignée ; pour les lemmes (l),
        # les formes w (mêmes indices, mais seules les formes se comparent au gold)
        self.layer = "g" if layer == "g" else "w"
        self._attached = {}  # (verset TM, verset LXX) -> (hb, gr, hb_unit, gr_unit), calculé une fois

    @classmethod
    def from_store(cls, store, he_book: str, lxx_book: str, layer: str = "w") -> "Evaluator":
        """Évaluateur d'un livre, données lues par un DataStore (store.py) ;
        doubles textes : ("Judg", "JudgA")."""
        return cls(store.gold(lxx_book), store.corpus("he", he_book),
                   store.corpus("lxx", lxx_book), layer)

    # --- un verset ---

    def _verse(self, rec):
        """Tokens et rattachement au gold d'une ligne du JSONL
        (alignment.AlignmentRecord), ou None si le verset n'est pas évaluable
        (pas de gold, ou tokens ≠ export)."""
        key, lxx_key = rec.key, rec.lxx_key   # verset TM, verset LXX apparié
        if not self.gold.covers(key, lxx_key):
            return None, "verset_sans_gold"
        if (key, lxx_key) not in self._attached:
            hb = self.he[key].tokens(self.layer) if key in self.he else []
            gr = self.lxx[lxx_key].tokens(self.layer) if lxx_key in self.lxx else []
            # rattachement au gold (projection lettre par lettre, coûteuse) : une
            # fois par verset, partagé par evaluate et export_csv
            self._attached[key, lxx_key] = (hb, gr, *self.gold.attach(key, hb, gr, lxx_key))
        hb, gr, hb_unit, gr_unit = self._attached[key, lxx_key]
        if len(rec.src) != len(hb) or len(rec.tgt) != len(gr):
            return None, "tokens_differents_de_l_export"
        return (key, lxx_key, hb, gr, hb_unit, gr_unit), None

    def count_verse(self, links, hb_unit, gr_unit, key, lxx_key=None) -> Counter:
        """Compte un verset. links = [(i, j)] ; hb_unit[i], gr_unit[j] = uid ou None.
        key = "ch.vs" du verset TM, lxx_key celui du verset LXX apparié (par
        défaut, même numéro)."""
        units, recon = self.gold.units, self.gold.recon
        c = Counter()
        found = set()      # unités align ayant au moins un lien juste interne
        touched_hb, touched_gr = set(), set()
        for i, j in links:
            uh, ug = hb_unit[i], gr_unit[j]
            if uh is None or ug is None:
                c["liens_ignores"] += 1
                continue
            touched_hb.add(i)
            touched_gr.add(j)
            if uh == ug and units[uh]["type"] == "align":
                c["justes"] += 1
                found.add(uh)
            elif (uh, ug) in recon:
                c["justes"] += 1
                c["justes_reconstruits"] += 1
            else:
                c["faux"] += 1

        # rappel par bloc : unités align ayant des tokens rattachés des deux côtés
        hb_of, gr_of = defaultdict(set), defaultdict(set)
        for i, u in enumerate(hb_unit):
            if u:
                hb_of[u].add(i)
        for j, u in enumerate(gr_unit):
            if u:
                gr_of[u].add(j)
        for uid, u in self.gold.verse_units(key):
            if u["type"] != "align" or "~" in u["n"]:
                continue
            if hb_of[uid] and gr_of[uid]:
                c["blocs_evaluables"] += 1
                c["blocs_trouves"] += uid in found
            elif hb_of[uid] and u["ref_lxx"].split(".", 1)[1] != (lxx_key or key):
                c["blocs_hors_portee"] += 1   # grec dans un autre verset LXX

        # non-alignements : tokens des unités plus / minus touchés par aucun lien
        for i, uid in enumerate(hb_unit):
            if uid and units[uid]["type"] == "minus":
                c["nonalign_tokens"] += 1
                c["nonalign_respectes"] += i not in touched_hb
        for j, uid in enumerate(gr_unit):
            if uid and units[uid]["type"] == "plus":
                c["nonalign_tokens"] += 1
                c["nonalign_respectes"] += j not in touched_gr

        # AER (Och & Ney) : P = couples internes aux unités align + liens reconstruits,
        # S = unités qui restent 1↔1 après tokenisation
        predicted = {(i, j) for i, j in links if hb_unit[i] and gr_unit[j]}
        possible = {(i, j) for i, j in predicted if self.gold.is_correct(hb_unit[i], gr_unit[j])}
        sure = {(min(hb_of[u]), min(gr_of[u])) for u in hb_of
                if u in gr_of and len(hb_of[u]) == 1 and len(gr_of[u]) == 1
                and units[u]["type"] == "align"}
        c["aer_A"] += len(predicted)
        c["aer_S"] += len(sure)
        c["aer_AinP"] += len(possible)
        c["aer_AinS"] += len(predicted & sure)

        c["tokens_hb"] += len(hb_unit)
        c["tokens_hb_rattaches"] += sum(u is not None for u in hb_unit)
        c["tokens_gr"] += len(gr_unit)
        c["tokens_gr_rattaches"] += sum(u is not None for u in gr_unit)
        return c

    # --- un passage ---

    def evaluate(self, jsonl) -> dict:
        """Comptes et mesures, par méthode, pour les versets d'un JSONL."""
        counts = defaultdict(Counter)  # une entrée par méthode présente dans le JSONL
        skipped = Counter()
        for rec in read_jsonl(jsonl):
            verse, reason = self._verse(rec)
            if verse is None:
                skipped[reason] += 1
                continue
            key, lxx_key, _, _, hb_unit, gr_unit = verse
            for m, links in rec.links.items():
                counts[m] += self.count_verse(links, hb_unit, gr_unit, key, lxx_key)
                counts[m]["versets"] += 1
        return {"versets_ignores": dict(skipped),
                "methodes": {m: {"mesures": measures(c), "comptes": dict(c)}
                             for m, c in counts.items() if c["versets"]}}

    def export_csv(self, jsonl, csv_path) -> None:
        """CSV de relecture : une ligne par mot hébreu et par méthode, avec les
        mots grecs alignés, le bloc CATSS et le verdict ; puis une ligne par
        verset pour les mots grecs sans lien."""
        units = self.gold.units
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:  # -sig : lisible par Excel
            w = csv.writer(f, delimiter=";")
            w.writerow(["ref", "methode", "n", "hebreu", "grec_aligne", "bloc_catss",
                        "catss_hebreu", "catss_grec", "verdict"])
            for rec in read_jsonl(jsonl):
                verse, _ = self._verse(rec)
                if verse is None:
                    continue
                _, _, hb, gr, hb_unit, gr_unit = verse
                for m, links in rec.links.items():
                    for i, tok in enumerate(hb):
                        js = [j for a, j in links if a == i]
                        uid = hb_unit[i]
                        u = units.get(uid) if uid else None
                        if uid is None:
                            verdict = "?"
                        elif not js:
                            verdict = "ok (minus)" if u["type"] == "minus" else "non aligné"
                        else:
                            ok = [gr_unit[j] is not None and self.gold.is_correct(uid, gr_unit[j])
                                  for j in js]
                            verdict = "juste" if all(ok) else "faux"
                        w.writerow([rec.ref, m, i, tok, " ".join(gr[j] for j in js),
                                    u["n"] if u else "", u["hb"] if u else "", u["gr"] if u else "",
                                    verdict])
                    linked = {j for _, j in links}
                    orphans = [gr[j] for j in range(len(gr)) if j not in linked]
                    if orphans:
                        w.writerow([rec.ref, m, "", "", "", "", "", "", "grec sans lien : " + " ".join(orphans)])
