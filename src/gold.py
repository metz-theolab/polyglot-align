"""Gold standard CATSS nettoyé (data/gold_clean/<livre>.json).

Gold rattache les tokens d'un verset à leurs blocs (unités CATSS) et dit si un
lien est juste. Voir DECISIONS.md, « Évaluation par blocs CATSS » (étape 1 :
projection ; étape 2 : jugement des liens).
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path


# --- Squelettes de comparaison (fonctions pures) -----------------------------


def heb_letters(text: str) -> str:
    """Lettres hébraïques seules (sans points, accents, shin/sin), finales = non finales."""
    text = text.translate(str.maketrans("ךםןףץ", "כמנפצ"))
    return re.sub(r"[^א-ת]", "", text)


def grc_letters(text: str) -> str:
    """Lettres grecques seules, sans accents, minuscules, σ = ς."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("ς", "σ")
    return re.sub(r"[^α-ω]", "", text)


def project(tokens: list, pieces: list, letters) -> list:
    """Apparie, dans l'ordre et lettre par lettre, des tokens à des morceaux de
    texte. pieces = [(id, texte)], dans l'ordre. Renvoie, pour chaque token,
    l'id de la majorité de ses lettres (None si aucune lettre appariée).
    Sert à rattacher les tokens aux unités du gold, et les tokens aux lignes
    du tableau du LLM."""
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


# --- Gold d'un livre ---------------------------------------------------------


class Gold:
    """Unités CATSS d'un livre.

    units : uid -> unité (uid = "ch.vs#n") ;
    recon : couples (uid hébreu, uid grec) des liens reconstruits {...} ;
    les unités sont aussi rangées par verset, dans l'ordre du TM côté hébreu
    et dans l'ordre du grec (par ref_lxx, transpositions comprises) côté grec.
    """

    def __init__(self, path):
        (chapters,) = json.loads(Path(path).read_text(encoding="utf-8")).values()
        self.units, self.recon = {}, set()
        self._hb = defaultdict(list)   # "ch.vs" (TM)  -> [(uid, hb)] dans l'ordre du TM
        self._gr = defaultdict(list)   # "ch.vs" (LXX) -> [(uid, gr)] dans l'ordre du grec
        gr_rows = defaultdict(list)    # ref LXX -> [(clé d'ordre, uid, gr)]
        for ch, verses in chapters.items():
            for vs, us in verses.items():
                present = {u["n"] for u in us}
                for u in us:
                    uid = f"{ch}.{vs}#{u['n']}"
                    self.units[uid] = u
                    lxx = ".".join(u["ref_lxx"].split(".")[1:])
                    order = (int(ch) if ch.isdigit() else 0, int(vs) if vs.isdigit() else 0)
                    if "~" not in u["n"]:  # unité ordinaire
                        self._hb[f"{ch}.{vs}"].append((uid, u["hb"]))
                        pos = position(u.get("gr_from", u["n"]))
                        gr_rows[lxx].append((order + (pos,), uid, u["gr"]))
                        continue
                    # lien reconstruit "src~other" : relie l'unité src à l'unité other ;
                    # si other a été supprimée (renvoi vide absorbé), le lien porte son texte
                    src, other = u["n"].split("~")
                    src_id, other_id = f"{ch}.{vs}#{src}", f"{ch}.{vs}#{other}"
                    if "gr_from" in u:
                        gr_id = other_id if other in present else uid
                        self.recon.add((src_id, gr_id))
                        if gr_id == uid:
                            gr_rows[lxx].append((order + (position(other),), uid, u["gr"]))
                    else:
                        hb_id = other_id if other in present else uid
                        self.recon.add((hb_id, src_id))
                        if hb_id == uid:
                            self._hb[f"{ch}.{vs}"].append((uid, u["hb"]))
        for lxx, rows in gr_rows.items():
            self._gr[lxx] = [(uid, gr) for _, uid, gr in sorted(rows, key=lambda r: r[0])]

    @classmethod
    def load(cls, book: str, root="data") -> "Gold":
        """Gold d'un livre grec : Gold.load("Gen"), Gold.load("JudgA")."""
        return cls(Path(root) / "gold_clean" / f"{book}.json")

    def covers(self, key: str, lxx_key: str = None) -> bool:
        """Le gold a-t-il des unités pour le verset TM `key` et le verset LXX
        `lxx_key` (par défaut, même numéro) ?"""
        return key in self._hb and (lxx_key or key) in self._gr

    def attach(self, key: str, he_tokens: list, lxx_tokens: list, lxx_key: str = None):
        """Rattache chaque token du verset TM `key` ("ch.vs") et du verset LXX
        `lxx_key` (par défaut, même numéro) à son unité.
        Renvoie (hb_unit, gr_unit) : un uid (ou None) par token."""
        return (project(he_tokens, self._hb[key], heb_letters),
                project(lxx_tokens, self._gr[lxx_key or key], grc_letters))

    def is_correct(self, uh: str, ug: str) -> bool:
        """Lien entre un token de l'unité uh et un token de l'unité ug : juste
        s'il reste dans une même unité `align`, ou si c'est un lien reconstruit."""
        return (uh == ug and self.units[uh]["type"] == "align") or (uh, ug) in self.recon

    def verse_units(self, key: str):
        """(uid, unité) des unités du verset TM `key`."""
        prefix = key + "#"
        return ((uid, u) for uid, u in self.units.items() if uid.startswith(prefix))
