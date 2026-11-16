"""Tests de polyglot_align.config (Config, Passage) et polyglot_align.corpus (Corpus, Verse).

Usage (depuis la racine du projet) : python -m unittest tests/test_config_corpus.py -v
"""
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.config import Config, Passage
from polyglot_align.corpus import Corpus, ref_key
from polyglot_align.store import DataStore

nfc = lambda s: unicodedata.normalize("NFC", s)


def config_from(text: str) -> Config:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(text)
    try:
        return Config.from_yaml(f.name)
    finally:
        Path(f.name).unlink()


class TestConfig(unittest.TestCase):
    def test_tokens_g_et_vocalisation(self):
        c = config_from("name: x\npassages: [{book: Gen}]\ntokens: g\nhebrew_vocalization: true")
        self.assertEqual((c.tokens, c.hebrew_vocalization), ("g", True))

    def test_valeurs_par_defaut(self):
        c = config_from("name: x\npassages: [{book: Gen, only: Gen.1}]")
        self.assertEqual((c.tokens, c.aligner, c.model, c.layer, c.methods), ("w", "simalign", "bert", 8, "mai"))
        self.assertTrue(c.greek_accents)
        self.assertFalse(c.hebrew_vocalization)

    def test_passage(self):
        self.assertEqual(Passage("Gen", only="Gen.1").label, "Gen.1")
        p = Passage("Judg", lxx_book="JudgA")
        self.assertEqual((p.lxx_book, p.label), ("JudgA", "JudgA"))
        self.assertEqual(Passage("Gen").lxx_book, "Gen")

    def test_option_inconnue(self):
        with self.assertRaisesRegex(ValueError, "inconnue.*token"):
            config_from("name: x\npassages: [{book: Gen}]\ntoken: w")

    def test_valeurs_invalides(self):
        for text, msg in [("tokens: x", "tokens"), ("aligner: llm", "llm_model"),
                          ("aligner: autre", "aligner"), ("methods: xyz", "methods")]:
            with self.assertRaisesRegex(ValueError, msg):
                config_from(f"name: x\npassages: [{{book: Gen}}]\n{text}")

    def test_sans_passage(self):
        with self.assertRaisesRegex(ValueError, "aucun passage"):
            config_from("name: x")

    def test_experiences_de_reference(self):
        for path in sorted((ROOT / "experiments").glob("*.yaml")):
            Config.from_yaml(path)  # ne doit pas lever d'erreur


class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.he = Corpus(ROOT / "data" / "he" / "Gen.json")
        cls.lxx = Corpus(ROOT / "data" / "lxx" / "Gen.json")

    def test_verset(self):
        v = self.he["1.1"]
        self.assertEqual((v.book, v.key, v.ref), ("Gen", "1.1", "Gen.1.1"))
        self.assertEqual(len(v.tokens("w")), len(v.tokens("l")))
        self.assertEqual(v.graphic_numbers(), "0 0 1 2 3 4 4 5 5 6 6".split())

    def test_mots_graphiques_hebreu(self):
        words = [nfc(w) for w in self.he["1.1"].graphic_words()]
        self.assertEqual(words[0], nfc("בְּרֵאשִׁ֖ית"))
        self.assertEqual(len(words), 7)

    def test_tokens_mots_graphiques(self):
        # tokens("g") : בְּ רֵאשִׁית -> בְּרֵאשִׁית ; 11 tokens w -> 7 mots graphiques
        g = [nfc(t) for t in self.he["1.1"].tokens("g")]
        self.assertEqual(len(g), 7)
        self.assertEqual(g[0], nfc("בְּרֵאשִׁ֖ית"))
        self.assertEqual(g[4], nfc("הַשָּׁמַ֖יִם"))
        # nom composé : un seul token, avec "_" (comme dans w)
        self.assertTrue(any("_" in t for t in self.he["4.22"].tokens("g")))
        # grec : un token = un mot graphique
        self.assertEqual(self.lxx["1.1"].tokens("g"), self.lxx["1.1"].tokens("w"))

    def test_mots_graphiques_grec(self):
        v = self.lxx["1.1"]
        self.assertEqual(v.graphic_words(), v.tokens("w"))  # LXX : un token = un mot graphique

    def test_nom_compose(self):
        # Gen 4:22 : תובל_קין -> « תובל קין » dans les mots graphiques
        words = self.he["4.22"].graphic_words("l")
        self.assertTrue(any(" " in w for w in words))

    def test_load_et_contains(self):
        self.assertIn("1.1", DataStore(ROOT / "data").corpus("he", "Gen"))
        self.assertNotIn("99.99", self.he)

    def test_ordre(self):
        self.assertLess(ref_key("Gen.2.10"), ref_key("Gen.10.2"))
        self.assertLess(ref_key("1.9"), ref_key("1.10"))


if __name__ == "__main__":
    unittest.main()
