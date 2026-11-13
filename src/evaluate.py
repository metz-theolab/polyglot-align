"""Évaluation d'un alignement contre le gold CATSS nettoyé, par blocs.

Applique DECISIONS.md, « Évaluation par blocs CATSS » : un lien prédit est
juste s'il reste à l'intérieur d'une unité CATSS de type `align` (ou s'il
correspond à un lien reconstruit `{...}`).

Bibliothèque, lancée par run.py. Entrées d'un passage :
    - sortie de align.py (JSONL) ;
    - exports data/he/<livre>.json et data/lxx/<livre grec>.json (couche w) ;
    - gold data/gold_clean/<livre grec>.json.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path



# --- Squelettes de comparaison -----------------------------------------------


def heb_letters(text: str) -> str:
    """Lettres hébraïques seules (sans points, accents, shin/sin), finales = non finales."""
    text = text.translate(str.maketrans("ךםןףץ", "כמנפצ"))
    return re.sub(r"[^א-ת]", "", text)


def grc_letters(text: str) -> str:
    """Lettres grecques seules, sans accents, minuscules, σ = ς."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("ς", "σ")
    return re.sub(r"[^α-ω]", "", text)


# --- Étape 1 : rattacher chaque token à son unité (projection) ---------------


def project(tokens: list, pieces: list, letters) -> list:
    """Apparie, dans l'ordre et lettre par lettre, les tokens d'un verset aux
    morceaux de texte du gold. pieces = [(unit_id, texte)], dans l'ordre.
    Renvoie, pour chaque token, l'unit_id de la majorité de ses lettres
    (None si aucune lettre appariée)."""
    a, a_tok = [], []
    for i, t in enumerate(tokens):
        for c in letters(t):
            a.append(c)
            a_tok.append(i)
    b, b_unit = [], []
    for uid, text in pieces:
        for c in letters(text):
            b.append(c)
            b_unit.append(uid)
    votes = [Counter() for _ in tokens]
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            votes[a_tok[blk.a + k]][b_unit[blk.b + k]] += 1
    return [v.most_common(1)[0][0] if v else None for v in votes]


def position(n: str) -> int:
    """Rang d'une unité dans l'ordre CATSS : "5" -> 5, "5+6" -> 5."""
    return int(re.match(r"\d+", n).group(0))


def gold_index(gold_book: dict):
    """Prépare le gold d'un livre.
    Renvoie :
      units   : uid -> unité (uid = "ch.vs#n") ;
      hb_by   : "ch.vs" (TM) -> [(uid, hb)] dans l'ordre du TM ;
      gr_by   : "ch.vs" (LXX) -> [(uid, gr)] dans l'ordre du grec ;
      recon   : couples (uid hébreu, uid grec) des liens reconstruits {...}."""
    units, hb_by, gr_by, recon = {}, defaultdict(list), defaultdict(list), set()
    gr_rows = defaultdict(list)  # ref LXX -> [(clé d'ordre, uid, gr)]
    for ch, verses in gold_book.items():
        for vs, us in verses.items():
            present = {u["n"] for u in us}
            for u in us:
                uid = f"{ch}.{vs}#{u['n']}"
                units[uid] = u
                lxx = ".".join(u["ref_lxx"].split(".")[1:])
                order = (int(ch) if ch.isdigit() else 0, int(vs) if vs.isdigit() else 0)
                if "~" not in u["n"]:  # unité ordinaire
                    hb_by[f"{ch}.{vs}"].append((uid, u["hb"]))
                    pos = position(u.get("gr_from", u["n"]))
                    gr_rows[lxx].append((order + (pos,), uid, u["gr"]))
                    continue
                # lien reconstruit "src~other" : relie l'unité src à l'unité other ;
                # si other a été supprimée (renvoi vide absorbé), le lien porte son texte
                src, other = u["n"].split("~")
                src_id, other_id = f"{ch}.{vs}#{src}", f"{ch}.{vs}#{other}"
                if "gr_from" in u:
                    gr_id = other_id if other in present else uid
                    recon.add((src_id, gr_id))
                    if gr_id == uid:
                        gr_rows[lxx].append((order + (position(other),), uid, u["gr"]))
                else:
                    hb_id = other_id if other in present else uid
                    recon.add((hb_id, src_id))
                    if hb_id == uid:
                        hb_by[f"{ch}.{vs}"].append((uid, u["hb"]))
    for lxx, rows in gr_rows.items():
        gr_by[lxx] = [(uid, gr) for _, uid, gr in sorted(rows, key=lambda r: r[0])]
    return units, hb_by, gr_by, recon


# --- Étapes 2 et 3 : juger les liens d'un verset, compter --------------------


def count_verse(links, hb_unit, gr_unit, units, recon, key) -> Counter:
    """Compte un verset. links = [(i, j)] ; hb_unit[i], gr_unit[j] = uid ou None.
    key = "ch.vs" du verset donné à l'aligneur (même numéro des deux côtés)."""
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
    for uid, u in units.items():
        if not uid.startswith(key + "#") or u["type"] != "align" or "~" in u["n"]:
            continue
        if hb_of[uid] and gr_of[uid]:
            c["blocs_evaluables"] += 1
            c["blocs_trouves"] += uid in found
        elif hb_of[uid] and u["ref_lxx"].split(".", 1)[1] != key:
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
    possible = {(i, j) for i, j in predicted
                if (hb_unit[i] == gr_unit[j] and units[hb_unit[i]]["type"] == "align")
                or (hb_unit[i], gr_unit[j]) in recon}
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


# --- Étape 4 : un livre ------------------------------------------------------


def load_tokens(path: Path) -> dict:
    """Export -> {"ch.vs": [tokens de w]}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    (book, chapters), = data.items()
    return {f"{ch}.{vs}": d["w"].split(" ") for ch, vs_ in chapters.items() for vs, d in vs_.items()}


def evaluate_book(jsonl: Path, he: Path, lxx: Path, gold: Path) -> dict:
    he_tok, lxx_tok = load_tokens(he), load_tokens(lxx)
    (gold_book,) = json.loads(gold.read_text(encoding="utf-8")).values()
    units, hb_by, gr_by, recon = gold_index(gold_book)

    counts = defaultdict(Counter)  # une entrée par méthode présente dans le JSONL
    skipped = Counter()
    for line in open(jsonl, encoding="utf-8"):
        d = json.loads(line)
        key = d["ref"].split(".", 1)[1]
        if key not in hb_by or key not in gr_by:
            skipped["verset_sans_gold"] += 1
            continue
        if len(d["src"]) != len(he_tok.get(key, [])) or len(d["tgt"]) != len(lxx_tok.get(key, [])):
            skipped["tokens_differents_de_l_export"] += 1
            continue
        hb_unit = project(he_tok[key], hb_by[key], heb_letters)
        gr_unit = project(lxx_tok[key], gr_by[key], grc_letters)
        for m in d["links"]:
            links = [tuple(map(int, l.split("-"))) for l in d["links"][m].split()]
            counts[m] += count_verse(links, hb_unit, gr_unit, units, recon, key)
            counts[m]["versets"] += 1

    return {"versets_ignores": dict(skipped),
            "methodes": {m: {"mesures": measures(c), "comptes": dict(c)}
                         for m, c in counts.items() if c["versets"]}}


# --- Export CSV pour la relecture --------------------------------------------


def export_csv(jsonl: Path, he: Path, lxx: Path, gold: Path, csv_path: Path) -> None:
    """Un CSV pour relire à la main : une ligne par mot hébreu et par méthode,
    avec les mots grecs alignés, le bloc CATSS et le verdict ; puis une ligne
    par verset pour les mots grecs sans lien."""
    import csv
    he_tok, lxx_tok = load_tokens(he), load_tokens(lxx)
    (gold_book,) = json.loads(gold.read_text(encoding="utf-8")).values()
    units, hb_by, gr_by, recon = gold_index(gold_book)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:  # -sig : lisible par Excel
        w = csv.writer(f, delimiter=";")
        w.writerow(["ref", "methode", "n", "hebreu", "grec_aligne", "bloc_catss",
                    "catss_hebreu", "catss_grec", "verdict"])
        for line in open(jsonl, encoding="utf-8"):
            d = json.loads(line)
            key = d["ref"].split(".", 1)[1]
            hb, gr = he_tok.get(key, []), lxx_tok.get(key, [])
            if key not in hb_by or key not in gr_by or len(hb) != len(d["src"]) or len(gr) != len(d["tgt"]):
                continue
            hb_unit = project(hb, hb_by[key], heb_letters)
            gr_unit = project(gr, gr_by[key], grc_letters)
            for m, raw in d["links"].items():
                links = [tuple(map(int, l.split("-"))) for l in raw.split()]
                for i, tok in enumerate(hb):
                    js = [j for a, j in links if a == i]
                    uid = hb_unit[i]
                    u = units.get(uid) if uid else None
                    if uid is None:
                        verdict = "?"
                    elif not js:
                        verdict = "ok (minus)" if u["type"] == "minus" else "non aligné"
                    else:
                        ok = [gr_unit[j] is not None and ((gr_unit[j] == uid and u["type"] == "align")
                              or (uid, gr_unit[j]) in recon) for j in js]
                        verdict = "juste" if all(ok) else "faux"
                    w.writerow([d["ref"], m, i, tok, " ".join(gr[j] for j in js),
                                u["n"] if u else "", u["hb"] if u else "", u["gr"] if u else "", verdict])
                linked = {j for _, j in links}
                orphans = [gr[j] for j in range(len(gr)) if j not in linked]
                if orphans:
                    w.writerow([d["ref"], m, "", "", "", "", "", "", "grec sans lien : " + " ".join(orphans)])
