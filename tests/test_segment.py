"""Tests de polyglot_align.segment et de son évaluation (sans charger dictabert-seg).

Usage (depuis la racine du projet) : python -m unittest tests/test_segment.py -v
"""
import re
import unittest
from pathlib import Path

from polyglot_align.evaluation.segmentation import cuts, is_train
from polyglot_align.segment import (CombinedSegmenter, TableSegmenter, bhsa_words, consonantal,
                                    consonantal_words, greek_verse, hebrew_verse, split_dicta_word,
                                    split_pointed)
from polyglot_align.store import DataStore

DATA = Path(__file__).resolve().parent.parent / "data"

EXAMPLES = [("בבית", ("ב", "בית")), ("בבית", ("ב", "בית")), ("בית", ("בית",)),
            ("ואת", ("ו", "את")), ("הארץ", ("ה", "ארץ")), ("בשמים", ("ב", "שמים")),
            ("בשמים", ("ב", "שמים")), ("בשמים", ("בשמים",))]


class TestConsonantique(unittest.TestCase):
    def test_vocalise_et_consonantique(self):
        self.assertEqual(consonantal("בַּבַּיִת"), "בבית")
        self.assertEqual(consonantal("בְּבֵית"), "בבית")
        self.assertEqual(consonantal("בְּרֵאשִׁ֖ית"), "בראשית")

    def test_maqqef_et_ponctuation(self):
        self.assertEqual(consonantal_words("אֶת־הָרָקִיעַ֒ וַֽיְהִי־כֵֽן׃"), ["את", "הרקיע", "ויהי", "כן"])


class TestTable(unittest.TestCase):
    def setUp(self):
        self.seg = TableSegmenter().fit(EXAMPLES)

    def test_article_absorbe_ignore(self):
        # בַּבַּיִת (article absorbé) et בְּבֵית donnent tous deux ב בית
        self.assertEqual(self.seg.segment("בַּבַּיִת"), ["ב", "בית"])
        self.assertEqual(self.seg.segment("בְּבֵית"), ["ב", "בית"])

    def test_decoupage_le_plus_frequent(self):
        self.assertEqual(self.seg.segment_word("בשמים"), ["ב", "שמים"])

    def test_forme_inconnue_prefixe_detache(self):
        self.assertEqual(self.seg.segment_word("ובבית"), ["ו", "ב", "בית"])   # ו + forme connue
        self.assertEqual(self.seg.segment_word("וכבית"), ["ו", "כ", "בית"])   # deux préfixes, reste connu
        self.assertEqual(self.seg.segment_word("ויקרא"), ["ויקרא"])          # reste inconnu : entier

    def test_texte_complet(self):
        self.assertEqual(self.seg.segment("וְאֵת הָאָרֶץ"), ["ו", "את", "ה", "ארץ"])


class TestDicta(unittest.TestCase):
    def test_prefixes_coupes_lettre_par_lettre(self):
        self.assertEqual(split_dicta_word(["וב", "שמים"], "ובשמים"), ["ו", "ב", "שמים"])
        self.assertEqual(split_dicta_word(["ברא"], "ברא"), ["ברא"])

    def test_sortie_incoherente(self):
        self.assertEqual(split_dicta_word(["ב", "שמים"], "בשמימ"), ["בשמימ"])


class FakeDicta:
    """dictabert-seg simulé : coupe un ו initial ; note les phrases reçues."""

    def __init__(self):
        self.calls = []

    def segment_sentences(self, sentences):
        self.calls.append(sentences)
        return [[["ו", w[1:]] if w.startswith("ו") else [w] for w in s] for s in sentences]


class TestCombinaison(unittest.TestCase):
    def setUp(self):
        self.dicta = FakeDicta()
        self.seg = CombinedSegmenter(TableSegmenter().fit(EXAMPLES), self.dicta)

    def test_table_pour_les_formes_connues_dicta_pour_les_autres(self):
        # בבית connu (table) ; והולידו inconnu (dictabert-seg, avec toute la phrase)
        self.assertEqual(self.seg.segment_words(["בבית", "והולידו"]), [["ב", "בית"], ["ו", "הולידו"]])
        self.assertEqual(self.dicta.calls, [[["בבית", "והולידו"]]])

    def test_dicta_non_appele_si_tout_est_connu(self):
        self.assertEqual(self.seg.segment_words(["ואת", "הארץ"]), [["ו", "את"], ["ה", "ארץ"]])
        self.assertEqual(self.dicta.calls, [])


class TestVerset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = DataStore(DATA)
        cls.table = TableSegmenter.from_store(cls.store)     # tout le corpus, comme dans l'app

    def test_report_sur_le_texte_ecrit(self):
        self.assertEqual(split_pointed("בַּבַּיִת", ["ב", "בית"]), ["בַּ", "בַּיִת"])
        self.assertEqual(split_pointed("וּבֵ֣ין", ["ו", "בין"]), ["וּ", "בֵ֣ין"])
        # lettre précomposée (שׂ U+FB2B) : gardée et comptée comme une lettre
        self.assertEqual(split_pointed("וַיּוּ\ufb2bַם", ["ו", "יושם"]), ["וַ", "יּוּ\ufb2bַם"])

    def test_objet_comme_le_corpus(self):
        v = hebrew_verse("בַּבַּיִת וְאֶת־הָאָרֶץ׃", self.table)
        self.assertEqual(v.tokens("w"), ["בַּ", "בַּיִת", "וְ", "אֶת", "הָ", "אָרֶץ"])
        self.assertEqual(v.layers["g"], "0 0 1 1 2 2")
        self.assertEqual(v.tokens("g"), ["בַּבַּיִת", "וְאֶת", "הָאָרֶץ"])
        self.assertEqual(v.ref, "A.1.1")

    def test_aller_retour_genese(self):
        """Texte t des versets de la Genèse -> couches w et g du corpus
        (versets dont t et w ont les mêmes lettres, sans nom composé) : mêmes
        mots graphiques partout, mêmes tokens pour 99,5 % des mots graphiques
        au moins (mesuré : 99,62 % ; le reste = ambiguïtés consonantiques,
        ex. Gn 3:11 הֲמִן -> la table choisit המן, Haman)."""
        letters = lambda x: re.sub(r"[^א-ת]", "", x)
        words = right = 0
        for v in self.store.corpus("he", "Gen").verses.values():
            if letters(v.layers["t"]) != letters(v.layers["w"]) or "_" in v.layers["w"]:
                continue
            got = hebrew_verse(v.layers["t"], self.table, v.ref)
            self.assertEqual(got.tokens("g"), v.tokens("g"), v.ref)
            for k in set(v.graphic_numbers()):
                words += 1
                right += ([t for t, g in zip(got.tokens("w"), got.graphic_numbers()) if g == k]
                          == [t for t, g in zip(v.tokens("w"), v.graphic_numbers()) if g == k])
        self.assertGreater(words, 18000)
        self.assertGreaterEqual(right / words, 0.995)

    def test_grec_comme_le_corpus(self):
        for key in ["1.1", "45.1"]:
            v = self.store.corpus("lxx", "Gen")[key]
            got = greek_verse(v.layers["t"])
            self.assertEqual((got.tokens("w"), got.graphic_numbers()), (v.tokens("w"), v.graphic_numbers()))
        self.assertEqual(greek_verse("ἐν ἀρχῇ, ἐποίησεν ὁ θεός.").tokens("w"),
                         ["ἐν", "ἀρχῇ", "ἐποίησεν", "ὁ", "θεός"])


class TestEvaluation(unittest.TestCase):
    def test_frontieres(self):
        self.assertEqual(cuts(("ו", "ב", "שמים")), {1, 2})
        self.assertEqual(cuts(("ברא",)), set())

    def test_chapitres(self):
        self.assertTrue(is_train("2"))
        self.assertFalse(is_train("1"))

    def test_mots_bhsa(self):
        words = bhsa_words(DataStore(DATA).corpus("he", "Gen")["1.1"])
        self.assertEqual(words[0], ("בראשית", ("ב", "ראשית")))
        self.assertEqual(words[-1], ("הארץ", ("ה", "ארץ")))
        self.assertEqual(len(words), 7)


if __name__ == "__main__":
    unittest.main()
