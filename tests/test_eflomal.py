"""Tests de l'aligneur eflomal (src/eflomal_align.py).

eflomal n'est pas lancé ici : un faux module `eflomal` écrit des liens fixés
d'avance, pour tester la préparation du corpus, la symétrisation et le
rattachement des liens aux versets sans dépendre du paquet (ni de son tirage
aléatoire).

Usage (depuis la racine du projet) : python -m unittest tests/test_eflomal.py -v
"""
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import Config, Passage                                    # noqa: E402
from corpus import Corpus, VerseMap                                   # noqa: E402
from aligners import make_aligner                                     # noqa: E402
from eflomal_align import EflomalAligner, grow_diag_final_and, parse_pharaoh  # noqa: E402

DATA = ROOT / "data"


class FakeEflomal:
    """Remplace eflomal.Aligner : relie le token i au token i (dans la limite
    du plus court) dans les deux sens, plus (0, 1) dans le sens direct."""
    seen = []

    def align(self, src, trg, links_filename_fwd, links_filename_rev, quiet=True):
        src, trg = list(src), list(trg)
        FakeEflomal.seen = src
        fwd, rev = [], []
        for s, t in zip(src, trg):
            n = min(len(s.split()), len(t.split()))
            diag = [f"{i}-{i}" for i in range(n)]
            fwd.append(" ".join(diag + ["0-1"]))
            rev.append(" ".join(diag))
        Path(links_filename_fwd).write_text("\n".join(fwd) + "\n", encoding="utf-8")
        Path(links_filename_rev).write_text("\n".join(rev) + "\n", encoding="utf-8")


class TestSymetrisation(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_pharaoh("0-0 2-1"), {(0, 0), (2, 1)})
        self.assertEqual(parse_pharaoh(""), set())

    def test_gdfa_ajoute_voisin_de_mot_non_aligne(self):
        fwd, rev = {(0, 0), (1, 1), (1, 2)}, {(0, 0), (1, 1)}
        self.assertEqual(grow_diag_final_and(fwd, rev), {(0, 0), (1, 1), (1, 2)})

    def test_gdfa_refuse_lien_entre_mots_deja_alignes(self):
        # (0, 1) : 0 et 1 sont déjà alignés par l'intersection
        fwd, rev = {(0, 0), (1, 1), (0, 1)}, {(0, 0), (1, 1)}
        self.assertEqual(grow_diag_final_and(fwd, rev), {(0, 0), (1, 1)})

    def test_final_and_lien_isole(self):
        # (3, 3) n'est voisin de rien mais ses deux mots sont libres
        fwd, rev = {(0, 0), (3, 3)}, {(0, 0)}
        self.assertEqual(grow_diag_final_and(fwd, rev), {(0, 0), (3, 3)})


class TestEflomalAligner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules["eflomal"] = types.SimpleNamespace(Aligner=FakeEflomal)
        cls.aligner = EflomalAligner(layer="w", greek_accents=False)
        cls.verse_map = VerseMap.load(DATA)
        cls.aligner.fit(cls.verse_map, DATA)
        cls.he, cls.lxx = Corpus.load("he", "Gen", DATA), Corpus.load("lxx", "Gen", DATA)

    @classmethod
    def tearDownClass(cls):
        del sys.modules["eflomal"]

    def test_apprend_sur_la_table(self):
        n = sum(len(self.verse_map.pairs(h, g)) for h, g in self.verse_map.book_pairs())
        self.assertEqual(len(FakeEflomal.seen), n - self.aligner.stats["versets vides ignorés"])
        self.assertIn(("Josh", "JoshA", "15.21"), self.aligner.links)

    def test_psaume_renumerote(self):
        # Ps 23:1 (TM) est appris avec Ps 22:1 (LXX)
        ps_he, ps_lxx = Corpus.load("he", "Ps", DATA), Corpus.load("lxx", "Ps", DATA)
        res = self.aligner.align(ps_he["23.1"], ps_lxx["22.1"])
        self.assertTrue(res.links["inter"])

    def test_tokens_sans_espace(self):
        self.assertTrue(all(" " not in t for line in FakeEflomal.seen for t in line.split()))

    def test_liens_du_verset(self):
        res = self.aligner.align(self.he["1.1"], self.lxx["1.1"])
        self.assertEqual(res.src, self.aligner.tokens(self.he["1.1"], self.lxx["1.1"])[0])
        self.assertEqual(res.tgt[:2], ["εν", "αρχη"])
        n = min(len(res.src), len(res.tgt))
        self.assertEqual(res.links["inter"], {(i, i) for i in range(n)})
        self.assertNotIn((0, 1), res.links["gdfa"])   # 0 et 1 déjà alignés

    def test_make_aligner(self):
        cfg = Config(name="t", passages=[Passage("Gen")], aligner="eflomal", tokens="l")
        cfg.check()
        a = make_aligner(cfg)
        self.assertIsInstance(a, EflomalAligner)
        self.assertEqual(a.layer, "l")


if __name__ == "__main__":
    unittest.main()
