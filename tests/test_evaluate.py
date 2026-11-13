"""Tests de l'évaluation par blocs (src/evaluate.py), voir DECISIONS.md
« Évaluation par blocs CATSS ».

Usage (depuis la racine du projet) : python -m unittest tests/test_evaluate.py -v
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from evaluate import (count_verse, gold_index, grc_letters, heb_letters,  # noqa: E402
                      load_tokens, measures, project)

DATA = ROOT / "data"


def gold(book: str) -> dict:
    (chapters,) = json.loads((DATA / "gold_clean" / f"{book}.json").read_text(encoding="utf-8")).values()
    return chapters


class TestExempleGn14(unittest.TestCase):
    """L'exemple de DECISIONS.md : blocs A `ו ירא` ↔ `καὶ εἶδεν`,
    B `אלהים` ↔ `ὁ θεὸς`, C `את ה אור` ↔ `τὸ φῶς`."""

    def setUp(self):
        self.units = {"1.4#A": {"n": "A", "type": "align", "ref_lxx": "Gen.1.4"},
                      "1.4#B": {"n": "B", "type": "align", "ref_lxx": "Gen.1.4"},
                      "1.4#C": {"n": "C", "type": "align", "ref_lxx": "Gen.1.4"}}
        # hébreu : ו ירא אלהים את ה אור ; grec : καὶ εἶδεν ὁ θεὸς τὸ φῶς
        self.hb = ["1.4#A", "1.4#A", "1.4#B", "1.4#C", "1.4#C", "1.4#C"]
        self.gr = ["1.4#A", "1.4#A", "1.4#B", "1.4#B", "1.4#C", "1.4#C"]

    def test_precision_et_rappel(self):
        # ירא–εἶδεν ✓, אלהים–θεὸς ✓, אור–φῶς ✓, את–θεὸς ✗
        links = [(1, 1), (2, 3), (5, 5), (3, 3)]
        c = count_verse(links, self.hb, self.gr, self.units, set(), "1.4")
        self.assertEqual((c["justes"], c["faux"]), (3, 1))
        self.assertEqual((c["blocs_trouves"], c["blocs_evaluables"]), (3, 3))
        m = measures(c)
        self.assertEqual(m["precision"], 0.75)
        self.assertEqual(m["rappel_blocs"], 1.0)

    def test_lien_non_trouve_non_penalise(self):
        # seul ירא–εἶδεν : précision 1, mais blocs B et C non trouvés
        c = count_verse([(1, 1)], self.hb, self.gr, self.units, set(), "1.4")
        self.assertEqual(measures(c)["precision"], 1.0)
        self.assertEqual((c["blocs_trouves"], c["blocs_evaluables"]), (1, 3))

    def test_token_inconnu_ignore(self):
        hb = self.hb[:5] + [None]
        c = count_verse([(5, 5)], hb, self.gr, self.units, set(), "1.4")
        self.assertEqual((c["justes"], c["faux"], c["liens_ignores"]), (0, 0, 1))


class TestNonAlignement(unittest.TestCase):
    def test_lien_vers_un_plus_est_faux(self):
        units = {"1.6#11": {"n": "11", "type": "align", "ref_lxx": "Gen.1.6"},
                 "1.6#12": {"n": "12", "type": "plus", "ref_lxx": "Gen.1.6"}}
        hb, gr = ["1.6#11"], ["1.6#11", "1.6#12"]
        c = count_verse([(0, 1)], hb, gr, units, set(), "1.6")
        self.assertEqual(c["faux"], 1)
        self.assertEqual((c["nonalign_respectes"], c["nonalign_tokens"]), (0, 1))


class TestProjection(unittest.TestCase):
    def test_gn_1_1(self):
        units, hb_by, gr_by, _ = gold_index(gold("Gen"))
        he, lxx = load_tokens(DATA / "he" / "Gen.json"), load_tokens(DATA / "lxx" / "Gen.json")
        hb = [units[u]["n"] for u in project(he["1.1"], hb_by["1.1"], heb_letters)]
        gr = [units[u]["n"] for u in project(lxx["1.1"], gr_by["1.1"], grc_letters)]
        # ב ראשית | ברא | אלהים | את ה שמים | ו את ה ארץ
        self.assertEqual(hb, ["1", "1", "2", "3", "4", "4", "4", "5", "5", "5", "5"])
        # ἐν ἀρχῇ | ἐποίησεν | ὁ θεὸς | τὸν οὐρανὸν | καὶ τὴν γῆν
        self.assertEqual(gr, ["1", "1", "2", "3", "3", "4", "4", "5", "5", "5"])

    def test_couverture_genese(self):
        units, hb_by, gr_by, _ = gold_index(gold("Gen"))
        he = load_tokens(DATA / "he" / "Gen.json")
        missing = sum(u is None for k in hb_by if k in he
                      for u in project(he[k], hb_by[k], heb_letters))
        total = sum(len(he[k]) for k in hb_by if k in he)
        self.assertLess(missing / total, 0.01)


class TestLiensReconstruits(unittest.TestCase):
    def test_isa_48_17(self):
        # #13 בדרך ↔ ἐν ᾗ {...ἐν αὐτῇ} ; #15 {...} ↔ ἐν αὐτῇ (absorbée)
        units, hb_by, gr_by, recon = gold_index(gold("Isa"))
        self.assertIn(("48.17#13", "48.17#13~15"), recon)
        self.assertIn(("48.17#13~15", "ἐν αὐτῇ"), [(u, g) for u, g in gr_by["48.17"]])

    def test_zeph_3_15(self):
        # #14 {...לא} עוד ↔ οὐκέτι : לא (#11) relié à οὐκέτι (#14)
        _, _, _, recon = gold_index(gold("Zeph"))
        self.assertIn(("3.15#11", "3.15#14"), recon)


if __name__ == "__main__":
    unittest.main()
