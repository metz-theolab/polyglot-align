"""Tests de polyglot_align.store (DataStore) et de l'index du gold par verset.

Usage (depuis la racine du projet) : python -m unittest tests/test_store.py -v
"""
import unittest
from pathlib import Path

from polyglot_align.store import DataStore

DATA = Path(__file__).resolve().parent.parent / "data"


class TestDataStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = DataStore(DATA)

    def test_chaque_fichier_lu_une_fois(self):
        self.assertIs(self.store.corpus("he", "Gen"), self.store.corpus("he", "Gen"))
        self.assertIs(self.store.gold("Gen"), self.store.gold("Gen"))
        self.assertIs(self.store.verse_map, self.store.verse_map)

    def test_verse_pairs_dans_l_ordre_de_la_table(self):
        pairs = self.store.verse_pairs("Gen", "Gen")
        keys = self.store.verse_map.pairs("Gen", "Gen")
        self.assertEqual([(hv.key, gv.key) for hv, gv in pairs], keys)

    def test_only_chapitre_et_verset(self):
        ch = self.store.verse_pairs("Gen", "Gen", only="Gen.1")
        self.assertEqual({hv.ref.rsplit(".", 1)[0] for hv, _ in ch}, {"Gen.1"})
        self.assertEqual(len(ch), 31)
        (vs,) = self.store.verse_pairs("Gen", "Gen", only="Gen.1.1")
        self.assertEqual(vs[0].ref, "Gen.1.1")
        # Gen.1 ne doit pas prendre Gen.10, Gen.11…
        self.assertNotIn("Gen.10.1", {hv.ref for hv, _ in ch})

    def test_psaume_renumerote(self):
        refs = {hv.ref: gv.ref for hv, gv in self.store.verse_pairs("Ps", "Ps", only="Ps.23")}
        self.assertEqual(refs["Ps.23.1"], "Ps.22.1")

    def test_table_pairs_toute_la_table(self):
        n = sum(len(self.store.verse_map.pairs(h, g)) for h, g in self.store.verse_map.book_pairs())
        pairs = list(self.store.table_pairs())
        self.assertEqual(len(pairs), n)
        self.assertIn(("Josh", "JoshA"), {(hv.book, gv.book) for hv, gv in pairs})


class TestGoldParVerset(unittest.TestCase):
    def test_index_egal_au_parcours_complet(self):
        """verse_units (index) donne les mêmes unités, dans le même ordre, que
        le parcours de toutes les unités du livre."""
        gold = DataStore(DATA).gold("Gen")
        for key in ["1.1", "3.6", "10.1", "50.26"]:
            expected = [(uid, u) for uid, u in gold.units.items() if uid.startswith(key + "#")]
            self.assertEqual(gold.verse_units(key), expected)
        self.assertEqual(gold.verse_units("99.99"), [])


if __name__ == "__main__":
    unittest.main()
