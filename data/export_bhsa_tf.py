"""Export de la BHSA (Text-Fabric) en JSON : un fichier par livre.

Format : {"Gen": {"1": {"1": {
    "t": "בְּרֵאשִׁ֖ית בָּרָ֣א …",   texte original
    "w": "בְּ רֵאשִׁ֖ית בָּרָ֣א …",  un token par mot BHSA (proclitiques séparés)
    "l": "ב ראשׁית ברא …",         lexème de chaque token
    "g": "0 0 1 …"                 numéro du mot graphique de chaque token
}}}}
w, l et g ont le même nombre de tokens. Le maqqef sépare deux mots graphiques.

Usage : python export_bhsa_tf.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from tf.app import use

CORPUS = "ETCBC/bhsa"
VERSION = "2021"
OUT_DIR = Path("he")

# Noms de livres (sans "_", en minuscules) -> abréviations OSIS, communs BHSA / LXX
ABBREV = {
    "genesis": "Gen", "exodus": "Exod", "leviticus": "Lev", "numbers": "Num",
    "deuteronomy": "Deut", "joshua": "Josh", "judges": "Judg", "ruth": "Ruth",
    "1samuel": "1Sam", "2samuel": "2Sam", "1kings": "1Kgs", "2kings": "2Kgs",
    "1chronicles": "1Chr", "2chronicles": "2Chr", "ezra": "Ezra", "nehemiah": "Neh",
    "esther": "Esth", "job": "Job", "psalms": "Ps", "proverbs": "Prov",
    "ecclesiastes": "Eccl", "songofsongs": "Song", "isaiah": "Isa", "jeremiah": "Jer",
    "lamentations": "Lam", "ezekiel": "Ezek", "daniel": "Dan", "hosea": "Hos",
    "joel": "Joel", "amos": "Amos", "obadiah": "Obad", "jonah": "Jonah",
    "micah": "Mic", "nahum": "Nah", "habakkuk": "Hab", "zephaniah": "Zeph",
    "haggai": "Hag", "zechariah": "Zech", "malachi": "Mal", "cant": "Song", "qoh": "Eccl",
}

A = use(CORPUS, version=VERSION, silent="deep")
T, F, L = A.api.T, A.api.F, A.api.L

COMPOUND_SEP = re.compile(r"[\s־׀]+")  # espace, maqqef, paseq (noms composés)


def export_verse(v) -> dict:
    """Couches parallèles d'un verset (même nombre de tokens dans w, l, g)."""
    w_toks, l_toks, g_toks = [], [], []
    g = 0
    for w in L.d(v, otype="word"):
        # qere partout (DECISIONS.md) : forme et séparateur du qere s'il existe
        qere = F.qere_utf8.v(w)
        if qere is not None:
            form, trailer = qere, F.qere_trailer_utf8.v(w)
        else:
            form, trailer = F.g_word_utf8.v(w), F.trailer_utf8.v(w)
        if not form:  # article caché (בַּ = ב + ה), ketiv sans qere : ignoré
            continue
        # noms propres composés (בית אל, בית־אל, חצור׀ חדתה) : un seul mot BHSA -> "_"
        # quel que soit le séparateur interne (espace, maqqef, paseq)
        w_toks.append(COMPOUND_SEP.sub("_", form))
        l_toks.append(F.lex_utf8.v(w).replace(" ", "_"))
        g_toks.append(str(g))
        if trailer:  # espace, maqqef, sof pasuq… : fin du mot graphique
            g += 1
    assert all(" " not in t for t in w_toks + l_toks), f"espace dans un token : {T.sectionFromNode(v)}"
    return {
        "t": " ".join(T.text(v, fmt="text-orig-full").split()),  # texte original (qere)
        "w": " ".join(w_toks),             # forme de chaque mot BHSA / tokenisation
        "l": " ".join(l_toks),             # lexème consonantique
        "g": " ".join(g_toks),             # numéro du mot graphique
    }


books = defaultdict(lambda: defaultdict(dict))
for v in F.otype.s("verse"):
    book, ch, vs = T.sectionFromNode(v)
    book_id = ABBREV[book.replace("_", "").lower()]  # KeyError si livre inconnu
    books[book_id][str(ch)][str(vs)] = export_verse(v)

OUT_DIR.mkdir(parents=True, exist_ok=True)
for book_id, chapters in books.items():
    path = OUT_DIR / f"{book_id}.json"
    path.write_text(json.dumps({book_id: chapters}, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"{len(books)} livres exportés dans {OUT_DIR}")
