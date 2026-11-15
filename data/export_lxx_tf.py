"""Export de la LXX de Rahlfs (Text-Fabric, CenterBLC) en JSON : un fichier par livre.

Format : {"Gen": {"1": {"1": {
    "t": "ἐν ἀρχῇ ἐποίησεν …",   texte original
    "w": "ἐν ἀρχῇ ἐποίησεν …",   un token par mot LXX
    "l": "ἐν ἀρχή ποιέω …",      lexème de chaque token
    "g": "0 1 2 …"               numéro du mot graphique de chaque token
}}}}
w, l et g ont le même nombre de tokens. Dans la LXX, un mot TF = un mot graphique.

Usage (depuis data/) : python export_lxx_tf.py
"""
import json
from collections import defaultdict
from pathlib import Path

from tf.app import use

CORPUS = "CenterBLC/LXX"
VERSION = "1935"
OUT_DIR = Path("lxx")
NON_ALIGNED_DIR = OUT_DIR / "non_aligned"   # livres sans équivalent hébreu (Sir, Wis, 1Mac…)

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

# Livres grecs avec un équivalent hébreu sans être dans ABBREV : 2 Esdras (= Esdras–Néhémie),
# Daniel de Théodotion ; les textes A (JoshA, JudgA) suivent leur livre
WITH_HEBREW = set(ABBREV.values()) | {"2Esdr", "DanTh"}

A = use(CORPUS, version=VERSION, silent="deep")
T, F, L = A.api.T, A.api.F, A.api.L


def export_verse(v) -> dict:
    """Couches parallèles d'un verset (même nombre de tokens dans w, l, g)."""
    words = L.d(v, otype="word")
    w_toks = [F.word.v(w) for w in words]
    l_toks = [F.lex_utf8.v(w) for w in words]
    assert all(" " not in t for t in w_toks + l_toks), f"espace dans un token : {T.sectionFromNode(v)}"
    return {
        "t": " ".join(T.text(v).split()),             # texte original
        "w": " ".join(w_toks),                        # forme de chaque mot
        "l": " ".join(l_toks),                        # lexème
        "g": " ".join(str(i) for i in range(len(words))),  # un mot TF = un mot graphique
    }


books = defaultdict(lambda: defaultdict(dict))
for v in F.otype.s("verse"):
    book, ch, vs = T.sectionFromNode(v)
    book_id = ABBREV.get(book.lower(), book)  # livres sans équivalent (Sir, Wis…) : nom conservé
    # Doubles textes de Rahlfs (Juges ; Josué 15, 18-19) : CenterBLC donne B puis A
    # sous la même référence -> la 2e occurrence va dans JoshA / JudgA (comme CATSS)
    if str(vs) in books[book_id][str(ch)]:
        book_id += "A"
    assert str(vs) not in books[book_id][str(ch)], f"référence en double : {book_id}.{ch}.{vs}"
    books[book_id][str(ch)][str(vs)] = export_verse(v)

NON_ALIGNED_DIR.mkdir(parents=True, exist_ok=True)
for book_id, chapters in books.items():
    aligned = book_id in WITH_HEBREW or book_id.removesuffix("A") in ABBREV.values()
    path = (OUT_DIR if aligned else NON_ALIGNED_DIR) / f"{book_id}.json"
    path.write_text(json.dumps({book_id: chapters}, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"{len(books)} livres exportés dans {OUT_DIR} (sans équivalent hébreu : {NON_ALIGNED_DIR})")
