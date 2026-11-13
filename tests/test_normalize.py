"""Tests de src/normalize.py.

Usage (depuis la racine du projet) : python -m unittest tests/test_normalize.py -v
"""
import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from normalize import norm_grc, norm_heb  # noqa: E402

nfc = lambda s: unicodedata.normalize("NFC", s)


class TestHebreu(unittest.TestCase):
    def test_sans_vocalisation(self):
        self.assertEqual(norm_heb("בְּרֵאשִׁ֖ית"), "בראשית")

    def test_avec_vocalisation(self):
        # voyelles, dagesh, point du shin gardés ; accent (tipḥa) retiré
        self.assertEqual(norm_heb("בְּרֵאשִׁ֖ית", vocalization=True), nfc("בְּרֵאשִׁית"))
        # meteg retiré : וַֽיְהִי -> וַיְהִי
        self.assertEqual(norm_heb("וַֽיְהִי", vocalization=True), nfc("וַיְהִי"))

    def test_nom_compose(self):
        self.assertEqual(norm_heb("בֵּית_אֵל"), "בית אל")


class TestGrec(unittest.TestCase):
    def test_accents(self):
        self.assertEqual(norm_grc("ἀρχῇ"), nfc("ἀρχῇ"))
        self.assertEqual(norm_grc("ἀρχῇ", accents=False), "αρχη")


if __name__ == "__main__":
    unittest.main()
