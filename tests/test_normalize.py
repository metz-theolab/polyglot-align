"""Tests de polyglot_align.normalize.

Usage (depuis la racine du projet) : python -m unittest tests/test_normalize.py -v
"""
import unicodedata
import unittest

from polyglot_align.normalize import norm_grc, norm_heb

nfc = lambda s: unicodedata.normalize("NFC", s)


class TestHebreu(unittest.TestCase):
    def test_sans_vocalisation(self):
        self.assertEqual(norm_heb("בְּרֵאשִׁ֖ית"), "בראשית")

    def test_avec_vocalisation(self):
        # voyelles, dagesh, point du shin gardés ; accent (tipḥa) retiré
        self.assertEqual(norm_heb("בְּרֵאשִׁ֖ית", "vocalized"), nfc("בְּרֵאשִׁית"))
        # meteg retiré : וַֽיְהִי -> וַיְהִי
        self.assertEqual(norm_heb("וַֽיְהִי", "vocalized"), nfc("וַיְהִי"))

    def test_pointe_texte_tel_quel(self):
        # cantillation gardée, aucune normalisation Unicode
        self.assertEqual(norm_heb("בְּרֵאשִׁ֖ית", "pointed"), "בְּרֵאשִׁ֖ית")
        self.assertEqual(norm_heb("בֵּית_אֵל", "pointed"), "בֵּית אֵל")

    def test_nom_compose(self):
        self.assertEqual(norm_heb("בֵּית_אֵל"), "בית אל")

    def test_valeur_inconnue(self):
        with self.assertRaisesRegex(ValueError, "hebrew"):
            norm_heb("א", "oui")


class TestGrec(unittest.TestCase):
    def test_accents(self):
        self.assertEqual(norm_grc("ἀρχῇ"), nfc("ἀρχῇ"))
        self.assertEqual(norm_grc("ἀρχῇ", "unaccented"), "αρχη")
        with self.assertRaisesRegex(ValueError, "greek"):
            norm_grc("α", False)


if __name__ == "__main__":
    unittest.main()
