"""Tests de l'évaluation par blocs (polyglot_align.evaluation), voir
DECISIONS.md « Évaluation par blocs CATSS ».

Usage (depuis la racine du projet) : python -m unittest tests/test_evaluate.py -v
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.evaluation.evaluate import Evaluator, measures
from polyglot_align.evaluation.gold import Gold
from polyglot_align.store import DataStore

DATA = ROOT / "data"
STORE = DataStore(DATA)


def fake_gold(units: dict, recon=()) -> Gold:
    """Gold construit à la main (sans fichier), pour les cas d'école."""
    g = Gold.__new__(Gold)
    g.units, g.recon = units, set(recon)
    return g


def evaluator(gold: Gold) -> Evaluator:
    return Evaluator(gold, he=None, lxx=None)  # count_verse n'utilise pas les textes


class TestExempleGn14(unittest.TestCase):
    """L'exemple de DECISIONS.md : blocs A `ו ירא` ↔ `καὶ εἶδεν`,
    B `אלהים` ↔ `ὁ θεὸς`, C `את ה אור` ↔ `τὸ φῶς`."""

    def setUp(self):
        self.ev = evaluator(fake_gold({
            "1.4#A": {"n": "A", "type": "align", "ref_lxx": "Gen.1.4"},
            "1.4#B": {"n": "B", "type": "align", "ref_lxx": "Gen.1.4"},
            "1.4#C": {"n": "C", "type": "align", "ref_lxx": "Gen.1.4"}}))
        # hébreu : ו ירא אלהים את ה אור ; grec : καὶ εἶδεν ὁ θεὸς τὸ φῶς
        self.hb = ["1.4#A", "1.4#A", "1.4#B", "1.4#C", "1.4#C", "1.4#C"]
        self.gr = ["1.4#A", "1.4#A", "1.4#B", "1.4#B", "1.4#C", "1.4#C"]

    def test_precision_et_rappel(self):
        # ירא–εἶδεν ✓, אלהים–θεὸς ✓, אור–φῶς ✓, את–θεὸς ✗
        c = self.ev.count_verse([(1, 1), (2, 3), (5, 5), (3, 3)], self.hb, self.gr, "1.4")
        self.assertEqual((c["justes"], c["faux"]), (3, 1))
        self.assertEqual((c["blocs_trouves"], c["blocs_evaluables"]), (3, 3))
        m = measures(c)
        self.assertEqual(m["precision"], 0.75)
        self.assertEqual(m["rappel_blocs"], 1.0)

    def test_lien_non_trouve_non_penalise(self):
        # seul ירא–εἶδεν : précision 1, mais blocs B et C non trouvés
        c = self.ev.count_verse([(1, 1)], self.hb, self.gr, "1.4")
        self.assertEqual(measures(c)["precision"], 1.0)
        self.assertEqual((c["blocs_trouves"], c["blocs_evaluables"]), (1, 3))

    def test_token_inconnu_ignore(self):
        hb = self.hb[:5] + [None]
        c = self.ev.count_verse([(5, 5)], hb, self.gr, "1.4")
        self.assertEqual((c["justes"], c["faux"], c["liens_ignores"]), (0, 0, 1))


class TestNonAlignement(unittest.TestCase):
    def test_lien_vers_un_plus_est_faux(self):
        ev = evaluator(fake_gold({"1.6#11": {"n": "11", "type": "align", "ref_lxx": "Gen.1.6"},
                                  "1.6#12": {"n": "12", "type": "plus", "ref_lxx": "Gen.1.6"}}))
        c = ev.count_verse([(0, 1)], ["1.6#11"], ["1.6#11", "1.6#12"], "1.6")
        self.assertEqual(c["faux"], 1)
        self.assertEqual((c["nonalign_respectes"], c["nonalign_tokens"]), (0, 1))


class TestGold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold = STORE.gold("Gen")
        cls.he, cls.lxx = STORE.corpus("he", "Gen"), STORE.corpus("lxx", "Gen")

    def test_projection_gn_1_1(self):
        hb, gr = self.gold.attach("1.1", self.he["1.1"].tokens(), self.lxx["1.1"].tokens())
        n = lambda uids: [self.gold.units[u]["n"] for u in uids]
        # ב ראשית | ברא | אלהים | את ה שמים | ו את ה ארץ
        self.assertEqual(n(hb), ["1", "1", "2", "3", "4", "4", "4", "5", "5", "5", "5"])
        # ἐν ἀρχῇ | ἐποίησεν | ὁ θεὸς | τὸν οὐρανὸν | καὶ τὴν γῆν
        self.assertEqual(n(gr), ["1", "1", "2", "3", "3", "4", "4", "5", "5", "5"])

    def test_projection_mots_graphiques(self):
        # tokens: g : chaque mot graphique se rattache directement à son bloc
        hb, _ = self.gold.attach("1.1", self.he["1.1"].tokens("g"), self.lxx["1.1"].tokens("g"))
        self.assertEqual([self.gold.units[u]["n"] for u in hb], ["1", "2", "3", "4", "4", "5", "5"])

    def test_couverture_genese(self):
        missing = total = 0
        for key, v in self.he.verses.items():
            if self.gold.covers(key) and key in self.lxx:
                hb, _ = self.gold.attach(key, v.tokens(), self.lxx[key].tokens())
                missing += sum(u is None for u in hb)
                total += len(hb)
        self.assertLess(missing / total, 0.01)

    def test_is_correct(self):
        self.assertTrue(self.gold.is_correct("1.1#1", "1.1#1"))
        self.assertFalse(self.gold.is_correct("1.1#1", "1.1#2"))


class TestLiensReconstruits(unittest.TestCase):
    def test_isa_48_17(self):
        # #13 בדרך ↔ ἐν ᾗ {...ἐν αὐτῇ} ; #15 {...} ↔ ἐν αὐτῇ (absorbée)
        gold = STORE.gold("Isa")
        self.assertIn(("48.17#13", "48.17#13~15"), gold.recon)
        lxx = STORE.corpus("lxx", "Isa")["48.17"].tokens()
        he = STORE.corpus("he", "Isa")["48.17"].tokens()
        _, gr = gold.attach("48.17", he, lxx)
        self.assertEqual(gr[-2:], ["48.17#13~15", "48.17#13~15"])  # ἐν αὐτῇ, à la fin du verset

    def test_zeph_3_15(self):
        # #14 {...לא} עוד ↔ οὐκέτι : לא (#11) relié à οὐκέτι (#14)
        self.assertIn(("3.15#11", "3.15#14"), STORE.gold("Zeph").recon)


if __name__ == "__main__":
    unittest.main()
