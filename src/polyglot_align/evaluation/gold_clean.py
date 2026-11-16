"""Nettoyage du gold CATSS : data/gold/*.json -> data/gold_clean/<livre>.json

Applique les règles de DECISIONS.md (« Nettoyage du balisage CATSS », « `^` :
transpositions », « `{...}` », « Numérotation des versets CATSS », « Ketiv /
qere »). Les cas que DECISIONS.md ne tranche pas reçoivent une règle par défaut
ET un drapeau `todo` : rien n'est décidé en silence, et la forme brute est
toujours conservée (raw_hb, raw_gr) pour pouvoir revenir sur un choix.

Format de sortie : {"Gen": {"1": {"1": [unité, …]}}}, une unité =
    {"n": "13",              numéro(s) d'unité CATSS ("5+6" après fusion #)
     "hb": "בדרך", "gr": "ἐν ᾗ",
     "type": "align" | "plus" | "minus",   plus : hb vide ; minus : gr vide
     "kind": "sure" | "possible",
     "ref_mt": "Isa.48.17", "ref_lxx": "Isa.48.17",
     "gr_from" / "hb_from": "15"   (transposition, renvoi : unité d'origine)
     "flags": [...], "todo": [...],
     "raw_hb": "...", "raw_gr": "..."}

Usage (depuis la racine du projet) : polyglot-align clean-gold
"""
import json
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path

log = logging.getLogger(__name__)

GOLD = Path("data/gold")
OUT = Path("data/gold_clean")

# Noms CATSS -> noms des exports (data/he, data/lxx)
BOOKS = {"JoshB": "Josh", "JudgB": "Judg", "1Sam/K": "1Sam", "2Sam/K": "2Sam",
         "1/3Kgs": "1Kgs", "2/4Kgs": "2Kgs", "Ezr": "Ezra", "Qoh": "Eccl"}

INDICATOR = re.compile(r"\{([a-z*!#̣̈]+)\}")       # {t} {d} {p} {*} {**} {!}…
REF_TO = re.compile(r"\{\.\.\.([^}]*)\}")                    # {...X}, {...}
INLINE = re.compile(r"\{\.\.(?!\.)([a-z^̣]*)([^}]*)\}")  # {..pX} {..dX} {..^X}…
BRACKET = re.compile(r"\[\[?([^\]]*)\]\]?")                   # [6] [1.7] [[27]]…


# --- Outils ------------------------------------------------------------------


def key(text: str) -> str:
    """Forme de comparaison : sans points ni accents, minuscules, lettres
    finales = non finales (CATSS écrit ושׁמונימ, εἰσ)."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(str.maketrans("ךםןףץς", "כמנפצσ")).lower()
    return " ".join(text.split())


def contains(haystack: str, needle: str) -> bool:
    """needle apparaît dans haystack comme suite de mots entiers."""
    h, n = f" {key(haystack)} ", f" {key(needle)} "
    return n.strip() != "" and n in h


def new_unit(n, hb, gr, book, ch, vs) -> dict:
    return {"n": n, "hb": hb, "gr": gr, "raw_hb": hb, "raw_gr": gr,
            "ref_mt": f"{book}.{ch}.{vs}", "flags": [], "todo": [],
            "refs": [], "lxx_mark": None, "kind": "sure"}


# --- 1. Transpositions `^` (avant la colonne b) ------------------------------


def transpositions(units: list) -> list:
    """Cas 2 : `{..^X}` + unité `{...}` ↔ X  -> X dans l'unité qui porte {..^X}.
    Cas 3 : `^^^ ^ =X` ↔ G  +  `^ X` ↔ `^^^`  -> X ↔ G à la position hébraïque."""
    drop = set()
    for i, u in enumerate(units):
        # cas 2 : mot grec transposé
        for code, x in INLINE.findall(u["gr"]):
            if "^" not in code:
                continue
            j = next((j for j, o in enumerate(units) if j != i and j not in drop
                      and o["hb"].strip() == "{...}" and key(o["gr"]) == key(x)), None)
            if j is None:
                u["todo"].append("transposition_grecque_non_resolue")
                continue
            u["gr_from"] = units[j]["n"]
            drop.add(j)
        # cas 3 : mot hébreu transposé
        if u["hb"].split()[:1] == ["^^^"]:
            m = re.search(r"\^\s*=\s*(\S+)", u["hb"])
            x = m.group(1) if m else ""
            j = next((j for j, o in enumerate(units) if j != i and j not in drop
                      and o["gr"].strip() == "^^^" and contains(o["hb"].replace("^", " "), x)), None)
            if j is None:
                u["todo"].append("transposition_hebraique_non_resolue")
                continue
            target = units[j]
            target["gr"], target["gr_from"] = u["gr"], u["n"]
            target["flags"].append("transposition")
            drop.add(i)
    return [u for k, u in enumerate(units) if k not in drop]


# --- 2. Colonne b, puis fusion des lignes coupées `#` ------------------------


def cut_column_b(u: dict) -> None:
    """Tout ce qui suit `=` côté hébreu est la colonne b (rétroversions, notes)."""
    toks = u["hb"].split()
    k = next((k for k, t in enumerate(toks) if "=" in t), len(toks))  # ''=מלך
    if k < len(toks):
        u["flags"].append("colonne_b")
        if toks[-1] == "#":          # la marque de ligne coupée survit à la coupe
            toks, k = toks[:k] + ["#"], k + 1
    u["hb"] = " ".join(toks[:k])


def join(prev: dict, u: dict) -> None:
    """Ajoute l'unité u à la fin de prev."""
    prev["n"] += "+" + u["n"]
    for side in ("hb", "gr"):
        prev[side] = (prev[side] + " " + u[side]).strip()
        prev["raw_" + side] += " | " + u["raw_" + side]
    prev["flags"] += u["flags"] + ["ligne_coupee"]
    prev["todo"] += u["todo"]


def merge_hash(units: list) -> list:
    """Ligne coupée : `X #` + unité suivante, ou unité précédente + `# Y`,
    forment une seule unité."""
    out = []
    for u in units:
        toks = u["hb"].split()
        continues = toks[:1] == ["#"]          # `# Y` : suite de la ligne précédente
        if continues:
            u["hb"] = " ".join(toks[1:])
        opens_prev = out and out[-1].pop("_open", False)
        if out and (opens_prev or continues):
            join(out[-1], u)
            u = out.pop()
        toks = u["hb"].split()
        if toks[-1:] == ["#"]:
            u["_open"] = True
        u["hb"] = " ".join(t for t in toks if t != "#")
        out.append(u)
    if out:
        out[-1].pop("_open", None)
    return out


# --- 3. Nettoyage d'un côté --------------------------------------------------


def clean_side(u: dict, side: str) -> None:
    text = u[side]

    # renvois {...X} : mémorisés, résolus plus tard ; {...} vide = renvoi seul
    for x in REF_TO.findall(text):
        if x.strip():
            u["refs"].append((side, x.strip()))
        else:
            u["flags"].append(f"renvoi_vide_{side}")
    text = REF_TO.sub(" ", text)

    # {..code X} : X est du texte présent à cette position, on le garde
    def inline(m):
        code, x = m.group(1), m.group(2)
        if "^" in code:              # transposition déjà traitée (cas 2)
            return " " + x + " "
        if code.strip("̣") == "r" or side == "hb":
            u["todo"].append(f"indicateur_..{code}_{side}")  # sens non décidé
        u["flags"].append(f"..{code}")
        return " " + x + " "
    text = INLINE.sub(inline, text)

    # indicateurs {t} {d} {p} {*} {**}… -> métadonnées
    for code in INDICATOR.findall(text):
        u["flags"].append(code)
    text = INDICATOR.sub(" ", text)

    # crochets : numérotation LXX côté grec (ref_lxx), retirés côté hébreu
    marks = BRACKET.findall(text)
    if marks:
        if side == "gr":
            u["lxx_mark"] = BRACKET.search(text).group(0)
        else:
            u["flags"].append("crochet_hb")
    text = BRACKET.sub(" ", text)

    toks = []
    for t in text.split():
        if t in ("--+", "---", "''", "^", "^^^", "~", "#", "\u02B9", "\u0374", "\u0323"):
            if t == "~" or t == "^":
                u["flags"].append("ordre")
            continue
        if side == "hb" and t.startswith(",,"):  # ,,a : passage araméen (métadonnée)
            u["flags"].append("arameen")
            continue
        if side == "hb" and t[0] in ".<":      # note hors colonne b (.bm, <sp>)
            u["flags"].append("note_hb")
            continue
        toks.append(t)

    if side == "hb":
        toks = ketiv_qere(u, toks)
    u[side] = " ".join(toks)

    residue = set(re.sub(r"[\w\s'̀-ͯ᾽᾿’ʼ]", "", u[side]))
    if residue:
        u["todo"].append(f"residu_{side}:{''.join(sorted(residue))}")


def ketiv_qere(u: dict, toks: list) -> list:
    """`*K **Q` -> Q ; `*z **Q` -> Q (qere sans ketiv) ; `*K` seul -> K + todo."""
    if not any(t.startswith("*") for t in toks):
        return toks
    has_qere = any(t.startswith("**") for t in toks)
    out = []
    for t in toks:
        if t.startswith("**"):
            out.append(t[2:])
        elif t.startswith("*"):
            if not has_qere:
                out.append(t[1:])
                u["todo"].append("ketiv_sans_qere")
        else:
            out.append(t)
    u["flags"].append("ketiv_qere")
    return [t for t in out if t and t != "z"]


# --- 4. Renvois {...X} -> liens possibles ------------------------------------


def resolve_refs(units: list, book: str, ch: str, vs: str) -> list:
    """{...X} : X retrouvé dans le même verset -> lien *possible* ;
    sinon (ou unité marquée [n]) -> non aligné. Les unités de renvoi vide dont
    le contenu est ainsi rattaché disparaissent."""
    extra, used = [], set()
    for u in units:
        for side, x in u.pop("refs"):
            other = "gr" if side == "hb" else "hb"
            if u["lxx_mark"]:
                u["todo"].append("renvoi_hors_verset")
                continue
            j = next((j for j, o in enumerate(units) if o is not u and contains(o[side], x)), None)
            if j is None:
                u["flags"].append("renvoi_introuvable")
                continue
            link = new_unit(f"{u['n']}~{units[j]['n']}",
                            x if side == "hb" else u["hb"],
                            x if side == "gr" else u["gr"], book, ch, vs)
            link.update(kind="possible", flags=["renvoi"], raw_hb=u["raw_hb"], raw_gr=u["raw_gr"])
            link[f"{side}_from"] = units[j]["n"]
            link["ref_lxx"] = u["ref_lxx"]
            link.pop("refs")
            extra.append(link)
            if f"renvoi_vide_{other}" in units[j]["flags"]:
                used.add(j)
    for j, u in enumerate(units):
        for side in ("hb", "gr"):
            if f"renvoi_vide_{side}" in u["flags"] and j not in used:
                u["todo"].append("renvoi_vide_non_rattache")
    return [u for j, u in enumerate(units) if j not in used] + extra


# --- 5. Verset complet -------------------------------------------------------


def lxx_ref(mark: str, book: str, ch: str):
    """[6] -> book.ch.6 ; [1.7] -> book.1.7 ; autres formes -> None (todo)."""
    if mark.startswith("[["):
        return None
    m = re.fullmatch(r"\[(\d+)(?:\.(\d+))?\]", mark)
    if not m:
        return None
    return f"{book}.{m.group(1)}.{m.group(2)}" if m.group(2) else f"{book}.{ch}.{m.group(1)}"


def clean_verse(book: str, ch: str, vs: str, raw_units: dict) -> list:
    units = [new_unit(n, u["hb"], u["gr"], book, ch, vs) for n, u in raw_units.items()]
    units = transpositions(units)
    for u in units:
        cut_column_b(u)
    units = merge_hash(units)
    for u in units:
        clean_side(u, "hb")
        clean_side(u, "gr")
        mark = u["lxx_mark"]
        ref = lxx_ref(mark, book, ch) if mark else None
        if mark and ref is None:
            u["todo"].append(f"ref_lxx_forme:{mark}")
        u["ref_lxx"] = ref or u["ref_mt"]
    units = resolve_refs(units, book, ch, vs)
    for u in units:
        u.pop("lxx_mark", None)
        u["type"] = "plus" if not u["hb"] else "minus" if not u["gr"] else "align"
        if book == "Sir":
            u["todo"].append("ben_sira_balisage_propre")
    return units


# --- Programme ---------------------------------------------------------------


def main():
    # un fichier par livre, nommé comme les exports (data/he, data/lxx) :
    # 15.1Chron.json -> 1Chr.json ; les Psaumes (deux fichiers CATSS) -> Ps.json
    books, report = {}, Counter()
    for path in sorted(GOLD.glob("*.json")):
        for catss_book, chapters in json.loads(path.read_text(encoding="utf-8")).items():
            book = BOOKS.get(catss_book, catss_book)
            out = books.setdefault(book, {})
            for ch, verses in chapters.items():
                for vs, raw_units in verses.items():
                    units = clean_verse(book, ch, vs, raw_units)
                    out.setdefault(ch, {})[vs] = units
                    for u in units:
                        report["unités"] += 1
                        report[f"type:{u['type']}"] += 1
                        report[f"kind:{u['kind']}"] += 1
                        for t in u["todo"]:
                            report["todo:" + t.split(":")[0]] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):  # sortie générée : on repart de zéro
        old.unlink()
    for book, chapters in books.items():
        (OUT / f"{book}.json").write_text(json.dumps({book: chapters}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    (OUT / "_rapport.json").write_text(json.dumps(dict(report.most_common()), ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    log.info("%d livres écrits dans %s", len(books), OUT)
    for k, n in report.most_common():
        log.info("%8d  %s", n, k)
