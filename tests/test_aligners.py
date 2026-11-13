"""Tests de l'interface Aligner (src/aligners.py, src/llm_align.py).

Le LLM n'est pas appelé : sa réponse est simulée par un tableau fixe, pour que
le test soit rapide et reproductible. SimAlign n'est pas chargé ici (lourd) :
il est couvert par le test de non-régression (tests/check_non_regression.py).

Usage (depuis la racine du projet) : python -m unittest tests/test_aligners.py -v
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from aligners import Aligner, VerseAlignment, make_aligner  # noqa: E402
from config import Config, Passage                          # noqa: E402
from corpus import Corpus                                   # noqa: E402
from llm_align import OllamaAligner                         # noqa: E402

TABLE_GN_1_1 = {"rows": [
    {"hebrew": "בְּרֵאשִׁ֖ית", "greek": "ἐν ἀρχῇ"},
    {"hebrew": "בָּרָ֣א", "greek": "ἐποίησεν"},
    {"hebrew": "אֱלֹהִ֑ים", "greek": "ὁ θεὸς"},
    {"hebrew": "אֵ֥ת", "greek": ""},
    {"hebrew": "הַשָּׁמַ֖יִם", "greek": "τὸν οὐρανὸν"},
    {"hebrew": "וְאֵ֥ת", "greek": "καὶ"},
    {"hebrew": "הָאָֽרֶץ", "greek": "τὴν γῆν"},
]}


class FakeOllama(OllamaAligner):
    """OllamaAligner dont la réponse est fixée d'avance."""

    def __init__(self, answer: str):
        super().__init__("faux-modele")
        self.answer, self.prompts = answer, []

    def _ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


class TestOllamaAligner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hv = Corpus(ROOT / "data" / "he" / "Gen.json")["1.1"]
        cls.gv = Corpus(ROOT / "data" / "lxx" / "Gen.json")["1.1"]

    def test_est_un_aligner(self):
        self.assertTrue(issubclass(OllamaAligner, Aligner))

    def test_tableau_converti_en_liens(self):
        a = FakeOllama(json.dumps(TABLE_GN_1_1))
        res = a.align(self.hv, self.gv)
        self.assertIsInstance(res, VerseAlignment)
        links = set(res.links["llm"])
        # tokens : hébreu 0 בְּ 1 רֵאשִׁית 2 בָּרָא 3 אֱלֹהִים 4 אֵת 5 הַ 6 שָּׁמַיִם …
        #          grec   0 ἐν 1 ἀρχῇ 2 ἐποίησεν 3 ὁ 4 θεὸς 5 τὸν 6 οὐρανὸν …
        # ligne בְּרֵאשִׁית ↔ ἐν ἀρχῇ : les 2 tokens hébreux reliés aux 2 grecs
        self.assertTrue({(0, 0), (0, 1), (1, 0), (1, 1)} <= links)
        self.assertIn((2, 2), links)                       # בָּרָא ↔ ἐποίησεν
        self.assertNotIn(4, {i for i, _ in links})         # אֵת : ligne au grec vide
        self.assertNotIn((4, 5), links)
        self.assertEqual(res.extra["llm_table"], TABLE_GN_1_1["rows"])
        self.assertEqual(a.stats["versets"], 1)

    def test_prompt_en_mots_graphiques(self):
        a = FakeOllama(json.dumps(TABLE_GN_1_1))
        a.align(self.hv, self.gv)
        self.assertIn(" ".join(self.hv.graphic_words()), a.prompts[0])

    def test_reponse_invalide(self):
        a = FakeOllama("ceci n'est pas du JSON")
        res = a.align(self.hv, self.gv)
        self.assertEqual(res.links, {"llm": []})
        self.assertEqual((a.stats["reponses_invalides"], a.stats["versets_sans_reponse"]), (2, 1))


class TestMakeAligner(unittest.TestCase):
    def test_llm(self):
        cfg = Config("x", [Passage("Gen")], aligner="llm", llm_model="gemma4:12b", tokens="l")
        a = make_aligner(cfg)
        self.assertIsInstance(a, OllamaAligner)
        self.assertEqual((a.model, a.layer), ("gemma4:12b", "l"))


if __name__ == "__main__":
    unittest.main()
