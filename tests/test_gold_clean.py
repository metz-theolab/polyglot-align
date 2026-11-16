"""Tests du nettoyage du gold CATSS (polyglot_align.evaluation.gold_clean).

Chaque test reprend un exemple de DECISIONS.md, appliqué au verset réel du gold
brut (data/gold).

Usage (depuis la racine du projet) : python -m unittest tests/test_gold_clean.py -v
"""
import json
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.evaluation.gold_clean import BOOKS, clean_verse

RAW = {}
for path in sorted((ROOT / "data" / "gold").glob("*.json")):
    for book, chapters in json.loads(path.read_text(encoding="utf-8")).items():
        RAW.setdefault(book, {}).update(chapters)


def verse(catss_book: str, ch: str, vs: str) -> list:
    return clean_verse(BOOKS.get(catss_book, catss_book), ch, vs, RAW[catss_book][ch][vs])


def unit(units: list, n: str) -> dict:
    return next(u for u in units if u["n"] == n)


class TestPlusMinus(unittest.TestCase):
    def test_plus(self):  # Gen 1:6 #12 : --+ =;ויהי <1.7> ↔ καὶ ἐγένετο
        u = unit(verse("Gen", "1", "6"), "12")
        self.assertEqual((u["hb"], u["gr"], u["type"]), ("", "καὶ ἐγένετο", "plus"))

    def test_minus(self):  # Isa 48:17 #8 : יהוה ↔ ---
        u = unit(verse("Isa", "48", "17"), "8")
        self.assertEqual((u["hb"], u["gr"], u["type"]), ("יהוה", "", "minus"))

    def test_plus_arameen(self):  # DanTh 2:6 #5 : --+ ,,a ↔ μοι
        u = unit(verse("DanTh", "2", "6"), "5")
        self.assertEqual(u["type"], "plus")
        self.assertIn("arameen", u["flags"])


class TestColonneB(unittest.TestCase):
    def test_retroversion_supprimee(self):  # 1 Ch 4:31 #2 : ובחצר =ובחצי .ry
        self.assertEqual(unit(verse("1Chr", "4", "31"), "2")["hb"], "ובחצר")

    def test_ligne_coupee(self):  # 1 Ch 4:31 #5 `… #` + #6 `# .bm` -> une unité
        u = unit(verse("1Chr", "4", "31"), "5+6")
        nfc = lambda s: unicodedata.normalize("NFC", s)  # ordre des points shin/sin
        self.assertEqual((nfc(u["hb"]), u["gr"]), (nfc("בראי ובשׁערים"), "βαρουμσεωριμ"))
        self.assertIn("t", u["flags"])  # {t} translittération -> métadonnée


class TestTranspositions(unittest.TestCase):
    def test_mot_grec_transpose(self):  # Exod 9:32 : כי ↔ {..^γὰρ} ; #7 {...} ↔ γὰρ
        units = verse("Exod", "9", "32")
        u = unit(units, "5")
        self.assertEqual((u["hb"], u["gr"], u["gr_from"], u["kind"]), ("כי", "γὰρ", "7", "sure"))
        self.assertNotIn("7", [x["n"] for x in units])

    def test_mot_hebreu_transpose(self):  # 1 R 15:4 : #5 ^^^ ^ =לו ↔ αὐτῷ ; #8 ^ לו ↔ ^^^
        units = verse("1/3Kgs", "15", "4")
        u = unit(units, "8")
        self.assertEqual((u["hb"], u["gr"], u["gr_from"]), ("לו", "αὐτῷ", "5"))
        self.assertNotIn("5", [x["n"] for x in units])

    def test_particule_postpositive(self):  # Exod 9:32 #1 : ὁ ^ δὲ πυρὸς
        self.assertEqual(unit(verse("Exod", "9", "32"), "1")["gr"], "ὁ δὲ πυρὸς")


class TestRenvois(unittest.TestCase):
    def test_renvoi_grec_meme_verset(self):  # Isa 48:17 #13 {...ἐν αὐτῇ} / #15 {...} ↔ ἐν αὐτῇ
        units = verse("Isa", "48", "17")
        self.assertEqual(unit(units, "13")["gr"], "ἐν ᾗ")
        link = unit(units, "13~15")
        self.assertEqual((link["hb"], link["gr"], link["kind"]), ("בדרך", "ἐν αὐτῇ", "possible"))
        self.assertNotIn("15", [x["n"] for x in units])

    def test_renvoi_hebreu_meme_verset(self):  # Zeph 3:15 #14 {...לא} עוד ↔ οὐκέτι
        link = unit(verse("Zeph", "3", "15"), "14~11")
        self.assertEqual((link["hb"], link["gr"], link["kind"]), ("לא", "οὐκέτι", "possible"))


class TestKetivQere(unittest.TestCase):
    def test_qere(self):  # Qoh 4:17 : *רגליך **רגלך {*}
        u = unit(verse("Qoh", "4", "17"), "2")
        self.assertEqual(u["hb"], "רגלך")
        self.assertIn("*", u["flags"])  # {*} : le grec suit le ketiv (métadonnée)

    def test_qere_sans_ketiv(self):  # 2 S 8:3 : *z **פרת {**}
        self.assertEqual(unit(verse("2Sam/K", "8", "3"), "12")["hb"], "פרת")


class TestRefLxx(unittest.TestCase):
    def test_verset_lxx_different(self):  # Qoh 1:5 #8 : ἀνατέλλων [6]
        units = verse("Qoh", "1", "5")
        self.assertEqual(unit(units, "7")["ref_lxx"], "Eccl.1.5")
        self.assertEqual(unit(units, "8")["ref_lxx"], "Eccl.1.6")
        self.assertEqual(unit(units, "8")["gr"], "ἀνατέλλων")


class TestFormat(unittest.TestCase):
    def test_forme_brute_conservee(self):
        u = unit(verse("Gen", "1", "6"), "12")
        self.assertEqual(u["raw_hb"], "--+ =;ויהי <1.7>")

    def test_noms_de_livres(self):
        self.assertEqual(verse("Qoh", "1", "5")[0]["ref_mt"], "Eccl.1.5")
        self.assertEqual(verse("1/3Kgs", "15", "4")[0]["ref_mt"], "1Kgs.15.4")


if __name__ == "__main__":
    unittest.main()
