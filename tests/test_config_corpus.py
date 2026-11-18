"""Tests de polyglot_align.config (Config, Passage) et polyglot_align.corpus (Corpus, Verse).

Usage (depuis la racine du projet) : python -m unittest tests/test_config_corpus.py -v
"""
import tempfile
import unicodedata
import unittest
from pathlib import Path

from polyglot_align.config import Config, Passage
from polyglot_align.corpus import Corpus, Verse, ref_key
from polyglot_align.store import DataStore

ROOT = Path(__file__).resolve().parent.parent

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
        c = config_from("name: x\npassages: [{book: Gen}]\ntokens: g\nhebrew: vocalized")
        self.assertEqual((c.tokens, c.hebrew), ("g", "vocalized"))

    def test_valeurs_par_defaut(self):
        c = config_from("name: x\npassages: [{book: Gen, only: Gen.1}]")
        self.assertEqual((c.tokens, c.hebrew, c.greek), ("w", "unvocalized", "accented"))
        self.assertEqual(c.aligner, {"type": "simalign", "model": "bert", "bert_layer": 8,
                                     "methods": "mai", "device": "cpu"})

    def test_section_aligneur_completee(self):
        c = config_from("name: x\npassages: [{book: Gen}]\naligner: {type: llm, model: gemma4:12b}")
        self.assertEqual(c.aligner_type, "llm")
        self.assertEqual(c.aligner_params, {"model": "gemma4:12b", "url": "http://localhost:11434",
                                            "think": False, "seed": 1, "num_predict": 4096})

    def test_toutes_combinaisons_acceptees(self):
        """Tout aligneur accepte toutes les valeurs de hebrew et greek."""
        for aligner in ["{type: simalign}", "{type: eflomal}", "{type: llm, model: m}"]:
            for hebrew in ["pointed", "vocalized", "unvocalized"]:
                for greek in ["accented", "unaccented"]:
                    config_from(f"name: x\npassages: [{{book: Gen}}]\nhebrew: {hebrew}\n"
                                f"greek: {greek}\naligner: {aligner}")

    def test_ancien_format_converti(self):
        c = config_from("name: x\npassages: [{book: Gen}]\nmodel: xlmr\nlayer: 6\n"
                        "greek_accents: false\nhebrew_vocalization: true\nllm_model: ignoré")
        self.assertEqual((c.hebrew, c.greek), ("vocalized", "unaccented"))
        self.assertEqual(c.aligner, {"type": "simalign", "model": "xlmr", "bert_layer": 6,
                                     "methods": "mai", "device": "cpu"})
        # LLM : grec toujours accentué (greek_accents était ignoré), hébreu pointé par défaut
        c = config_from("name: x\npassages: [{book: Gen}]\naligner: llm\nllm_model: g\n"
                        "greek_accents: false\nmodel: ignoré")
        self.assertEqual((c.hebrew, c.greek, c.aligner["model"]), ("pointed", "accented", "g"))
        self.assertIsNone(c.aligner["num_predict"])   # pas de limite de génération à l'époque

    def test_passage(self):
        self.assertEqual(Passage("Gen", only="Gen.1").label, "Gen.1")
        p = Passage("Judg", lxx_book="JudgA")
        self.assertEqual((p.lxx_book, p.label), ("JudgA", "JudgA"))
        self.assertEqual(Passage("Gen").lxx_book, "Gen")

    def test_option_inconnue(self):
        with self.assertRaisesRegex(ValueError, "inconnue.*token"):
            config_from("name: x\npassages: [{book: Gen}]\ntoken: w")

    def test_valeurs_invalides(self):
        for text, msg in [("tokens: x", "tokens"), ("hebrew: oui", "hebrew"), ("greek: grc", "greek"),
                          ("aligner: {type: llm}", "model"), ("aligner: {type: autre}", "aligner"),
                          ("aligner: {type: simalign, methods: xyz}", "methods"),
                          ("aligner: {type: eflomal, model: x}", "inconnue"),
                          ("aligner: {type: llm, model: m, num_predict: 0}", "num_predict"),
                          ("aligner: {type: llm, model: m, num_predict: beaucoup}", "num_predict"),
                          ("aligner: {model: x}", "type")]:
            with self.assertRaisesRegex(ValueError, msg):
                config_from(f"name: x\npassages: [{{book: Gen}}]\n{text}")

    def test_sans_passage(self):
        with self.assertRaisesRegex(ValueError, "aucun passage"):
            config_from("name: x")

    def test_experiences_de_reference(self):
        for path in sorted((ROOT / "experiments").glob("*.yaml")):
            Config.from_yaml(path)  # ne doit pas lever d'erreur
        for path in sorted((ROOT / "tests" / "reference").glob("*/config.yaml")):
            Config.from_yaml(path)  # ancien format, converti


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

    def test_mots_separes_par_des_espaces(self):
        # Gn 1,7 : אֶת־הָרָקִיעַ = un mot de t, deux mots graphiques (2, 3)
        groups = self.he["1.7"].spaced_words()
        self.assertEqual(len(groups), len(self.he["1.7"].tokens("t")))
        self.assertEqual(groups[2], ([2], ["2", "3"]))
        # nom composé (1 Ch 1,50 : בַּעַל חָנָן, un token de w) : deux mots de t, un groupe ;
        # setuma ס en fin de verset : groupe sans mot graphique
        v = Verse("1Chr", "1", "50", {"t": "וַיָּמָת בַּעַל חָנָן וַיִּמְלֹךְ ס",
                                       "w": "וַ יָּמָת בַּעַל_חָנָן וַ יִּמְלֹךְ", "g": "0 0 1 2 2"})
        self.assertEqual(v.spaced_words(), [([0], ["0"]), ([1, 2], ["1"]), ([3], ["2"]), ([4], [])])
        bad = Verse("Gen", "1", "1", {"t": "אב", "w": "גד", "g": "0"})
        with self.assertRaises(ValueError):
            bad.spaced_words()

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
