"""Tests de la table d'équivalence des versets (data/make_verse_map.py,
corpus.VerseMap), voir DECISIONS.md « Appariement des versets par le gold ».

Usage (depuis la racine du projet) : python -m unittest tests/test_verse_map.py -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))
from corpus import VerseMap        # noqa: E402
from make_verse_map import verse_groups  # noqa: E402

DATA = ROOT / "data"


def unit(gr, ref_lxx):
    return {"gr": gr, "ref_lxx": ref_lxx}


class TestGroupes(unittest.TestCase):
    def test_groupes(self):
        chapters = {"1": {
            "1": [unit("a", "B.1.1")],                         # 1 ↔ 1
            "2": [unit("b", "B.1.3"), unit("c", "B.1.4")],     # 2 ↔ 2 avec le verset 3
            "3": [unit("d", "B.1.4")],
            "4": [unit("", "B.1.4")],                          # sans grec : 1 ↔ 0
        }}
        groups = sorted((sorted(h), sorted(g)) for h, g in verse_groups(chapters))
        self.assertEqual(groups, [(["1.1"], ["1.1"]), (["1.2", "1.3"], ["1.3", "1.4"]),
                                  (["1.4"], [])])


class TestVerseMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vm = VerseMap.load(DATA)

    def test_psaumes_renumerotes(self):
        self.assertIn(("23.1", "22.1"), self.vm.pairs("Ps", "Ps"))

    def test_textes_doubles(self):
        self.assertIn(("Josh", "JoshA"), self.vm.book_pairs())
        self.assertIn(("Judg", "JudgA"), self.vm.book_pairs())

    def test_un_pour_un(self):
        for he_book, lxx_book in self.vm.book_pairs():
            pairs = self.vm.pairs(he_book, lxx_book)
            self.assertEqual(len({h for h, _ in pairs}), len(pairs), lxx_book)
            self.assertEqual(len({g for _, g in pairs}), len(pairs), lxx_book)

    def test_mauvais_livre_hebreu(self):
        with self.assertRaises(KeyError):
            self.vm.pairs("Josh", "JudgA")

    def test_passages_de_reference_complets(self):
        # Gen 1, Gen 3, 1 S 9 : tous les versets restent appariés à eux-mêmes
        gen = dict(self.vm.pairs("Gen", "Gen"))
        sam = dict(self.vm.pairs("1Sam", "1Sam"))
        self.assertEqual([gen.get(f"1.{v}") for v in range(1, 32)], [f"1.{v}" for v in range(1, 32)])
        self.assertEqual([gen.get(f"3.{v}") for v in range(1, 25)], [f"3.{v}" for v in range(1, 25)])
        self.assertEqual([sam.get(f"9.{v}") for v in range(1, 28)], [f"9.{v}" for v in range(1, 28)])


if __name__ == "__main__":
    unittest.main()
