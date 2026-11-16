"""Tests de polyglot_align.textalign (align("texte A", "texte B")), sans eflomal
ni dictabert-seg : eflomal est remplacé par un faux (lien i-i), la
segmentation par la table seule.

Usage (depuis la racine du projet) : python -m unittest tests/test_textalign.py -v
"""
import json
import sys
import types
import unittest
from pathlib import Path

from polyglot_align.segment import TableSegmenter
from polyglot_align.store import DataStore
from polyglot_align.textalign import TextAligner

DATA = Path(__file__).resolve().parent.parent / "data"

HEBREW = "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
GREEK = "ἐν ἀρχῇ ἐποίησεν ὁ θεός."


class FakeEflomal:
    """Remplace eflomal.Aligner : relie le token i au token i dans les deux
    sens, plus (0, 1) dans le sens direct ; compte les apprentissages."""
    calls = []

    def align(self, src, trg, links_filename_fwd, links_filename_rev, quiet=True):
        src, trg = list(src), list(trg)
        FakeEflomal.calls.append((src, trg))
        fwd, rev = [], []
        for s, t in zip(src, trg):
            n = min(len(s.split()), len(t.split()))
            diag = [f"{i}-{i}" for i in range(n)]
            fwd.append(" ".join(diag + ["0-1"]))
            rev.append(" ".join(diag))
        Path(links_filename_fwd).write_text("\n".join(fwd) + "\n", encoding="utf-8")
        Path(links_filename_rev).write_text("\n".join(rev) + "\n", encoding="utf-8")


class TestTextAligner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules["eflomal"] = types.SimpleNamespace(Aligner=FakeEflomal)
        store = DataStore(DATA)
        cls.aligner = TextAligner(store, segmenter=TableSegmenter.from_store(store))

    @classmethod
    def tearDownClass(cls):
        del sys.modules["eflomal"]

    def setUp(self):
        FakeEflomal.calls = []

    def test_paire_saisie_ajoutee_a_la_table(self):
        res = self.aligner.align(HEBREW, GREEK)
        (src, trg), = FakeEflomal.calls
        self.assertEqual(src[-1], "ב ראשית ברא אלהים\n")        # dernière ligne : la paire saisie
        self.assertEqual(trg[-1], "εν αρχη εποιησεν ο θεος\n")
        self.assertGreater(len(src), 22000)                     # plus toute la table
        self.assertEqual(res.hebrew.tokens("w"), ["בְּ", "רֵאשִׁית", "בָּרָא", "אֱלֹהִים"])
        self.assertEqual(res.greek.tokens("w"), ["ἐν", "ἀρχῇ", "ἐποίησεν", "ὁ", "θεός"])

    def test_deux_symetrisations_inter_inclus_dans_gdfa(self):
        res = self.aligner.align(HEBREW, GREEK)
        self.assertEqual(res.links["inter"], [(0, 0), (1, 1), (2, 2), (3, 3)])
        self.assertTrue(set(res.links["inter"]) <= set(res.links["gdfa"]))
        self.assertEqual(res.pairs("inter")[:2], [("בְּ", "ἐν"), ("רֵאשִׁית", "ἀρχῇ")])

    def test_vue_par_mot_graphique(self):
        words = self.aligner.align(HEBREW, GREEK).by_graphic_word("inter")
        self.assertEqual(words[0], {"hebrew": "בְּרֵאשִׁית", "tokens": ["בְּ", "רֵאשִׁית"],
                                    "greek": ["ἐν", "ἀρχῇ"]})
        self.assertEqual(len(words), 3)

    def test_json_pour_l_api(self):
        d = json.loads(json.dumps(self.aligner.align(HEBREW, GREEK).to_dict(), ensure_ascii=False))
        self.assertEqual(set(d), {"hebrew", "greek", "links"})
        self.assertEqual(d["hebrew"]["graphic"], [0, 0, 1, 2])
        self.assertEqual(set(d["links"]), {"inter", "gdfa"})

    def test_plusieurs_paires_un_seul_apprentissage(self):
        res = self.aligner.align_many([(HEBREW, GREEK), ("וְאֵת הָאָרֶץ", "καὶ τὴν γῆν")])
        self.assertEqual(len(FakeEflomal.calls), 1)
        self.assertEqual([r.hebrew.ref for r in res], ["A.1.1", "A.1.2"])
        self.assertEqual(res[1].pairs("inter")[0], ("וְ", "καὶ"))

    def test_texte_vide_refuse(self):
        with self.assertRaisesRegex(ValueError, "hébreu"):
            self.aligner.align("…", GREEK)
        with self.assertRaisesRegex(ValueError, "grec"):
            self.aligner.align(HEBREW, "123")


if __name__ == "__main__":
    unittest.main()
