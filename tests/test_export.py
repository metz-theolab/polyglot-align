"""Tests des exports Text-Fabric (data/export_bhsa_tf.py, data/export_lxx_tf.py,
data/export_peshitta_tf.py).

Les scripts d'export lancent Text-Fabric dès l'import : on teste donc les fichiers
qu'ils produisent dans data/he et data/lxx (à régénérer avant de lancer les tests).

Usage (depuis la racine du projet) : python -m unittest tests/test_export.py -v
"""
import json
import re
import unicodedata
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def nfc(s: str) -> str:
    """Les exports ne sont pas normalisés Unicode (ordre des points hébreux,
    oxia/tonos grecs) : on compare en forme canonique NFC."""
    return unicodedata.normalize("NFC", s)


def load_dir(directory: Path) -> dict:
    """{"Gen": {"1": {"1": {...}}}, ...} pour tous les fichiers d'un dossier."""
    books = {}
    for path in sorted(directory.glob("*.json")):
        books.update(json.loads(path.read_text(encoding="utf-8")))
    return books


def verses(books: dict):
    """(référence, couches) pour chaque verset."""
    for book, chapters in books.items():
        for ch, vss in chapters.items():
            for vs, layers in vss.items():
                yield f"{book}.{ch}.{vs}", layers


class FormatChecks:
    """Règles communes aux deux exports (voir DECISIONS.md, format d'export)."""

    books: dict
    layers: set   # couches attendues ; toutes sauf t sont tokenisées

    def test_couches(self):
        for ref, d in verses(self.books):
            self.assertEqual(set(d), self.layers, ref)

    def test_meme_nombre_de_tokens(self):
        for ref, d in verses(self.books):
            n = len(d["w"].split(" "))
            for layer in self.layers - {"t", "w"}:
                self.assertEqual(len(d[layer].split(" ")), n, f"{ref} : {layer} ≠ w")

    def test_pas_de_token_vide(self):
        # split(" ") produit "" s'il y a une espace double, en tête ou en fin
        for ref, d in verses(self.books):
            for layer in self.layers - {"t"}:
                self.assertNotIn("", d[layer].split(" "), f"{ref} : token vide dans {layer}")

    def test_g_commence_a_zero_et_avance_de_un(self):
        for ref, d in verses(self.books):
            g = [int(x) for x in d["g"].split(" ")]
            self.assertEqual(g[0], 0, ref)
            for a, b in zip(g, g[1:]):
                self.assertIn(b - a, (0, 1), f"{ref} : g saute de {a} à {b}")


class TestBHSA(FormatChecks, unittest.TestCase):
    layers = {"t", "w", "l", "g"}

    @classmethod
    def setUpClass(cls):
        cls.books = load_dir(DATA / "he")

    def test_39_livres(self):
        self.assertEqual(len(self.books), 39)
        self.assertIn("Song", self.books)
        self.assertIn("Eccl", self.books)

    def test_gen_1_1(self):
        d = self.books["Gen"]["1"]["1"]
        gn_1_1 = "בְּ רֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַ שָּׁמַ֖יִם וְ אֵ֥ת הָ אָֽרֶץ"
        self.assertEqual(nfc(d["w"]), nfc(gn_1_1))
        self.assertEqual(nfc(d["l"]).split(" ")[:4], [nfc(x) for x in ["ב", "ראשׁית", "ברא", "אלהים"]])
        self.assertEqual(d["g"], "0 0 1 2 3 4 4 5 5 6 6")

    def test_maqqef_separe_deux_mots_graphiques(self):
        # Gen 1:7 se termine par וַֽיְהִי־כֵֽן : וַֽ יְהִי | כֵֽן
        g = self.books["Gen"]["1"]["7"]["g"].split(" ")
        self.assertEqual(g[-3], g[-2])
        self.assertEqual(int(g[-1]), int(g[-2]) + 1)

    def test_noms_propres_composes(self):
        # Gen 4:22 : תובל קין (Toubal-Caïn) = un seul token avec "_"
        self.assertIn("תובל_קין", self.books["Gen"]["4"]["22"]["l"].split(" "))

    def test_reconstruction_du_texte(self):
        """En recollant les tokens de même g, on retrouve les mots de t
        (au maqqef et à la ponctuation près)."""
        punct = re.compile(r"[׀׃׆]")  # paseq, sof pasuq, nun hafukha
        for ref, d in verses(self.books):
            words = {}
            for tok, g in zip(d["w"].split(" "), d["g"].split(" ")):
                words[g] = words.get(g, "") + tok
            rebuilt = " ".join(words.values()).replace("_", " ").split()
            original = punct.sub(" ", d["t"].replace("־", " ")).split()
            # setuma, petuḥa, nun inversé (Nb 10:34, 10:36 : codé par BHSA comme un נ ordinaire)
            original = [w for w in original if w not in ("ס", "פ", "נ")]
            self.assertEqual(rebuilt, original, ref)


class TestLXX(FormatChecks, unittest.TestCase):
    layers = {"t", "w", "l", "g"}

    @classmethod
    def setUpClass(cls):
        cls.aligned = set(load_dir(DATA / "lxx"))
        cls.non_aligned = set(load_dir(DATA / "lxx" / "non_aligned"))
        cls.books = {**load_dir(DATA / "lxx"), **load_dir(DATA / "lxx" / "non_aligned")}

    def test_noms_de_livres(self):
        for name in ("Song", "Eccl", "JoshA", "JudgA", "DanTh", "2Esdr"):
            self.assertIn(name, self.aligned)
        for name in ("Cant", "Qoh"):
            self.assertNotIn(name, set(self.books))

    def test_livres_sans_hebreu_a_part(self):
        # livres sans équivalent hébreu : dans lxx/non_aligned, pas dans lxx/
        for name in ("Sir", "Wis", "1Mac", "TobS", "Sus", "Bel", "Od", "PsSol", "1Esdr"):
            self.assertIn(name, self.non_aligned)
            self.assertNotIn(name, self.aligned)

    def test_t_egal_w(self):
        # CenterBLC : texte déjà tokenisé, sans ponctuation
        for ref, d in verses(self.books):
            self.assertEqual(d["t"], d["w"], ref)

    def test_g_un_mot_par_token(self):
        for ref, d in verses(self.books):
            n = len(d["w"].split(" "))
            self.assertEqual(d["g"], " ".join(str(i) for i in range(n)), ref)

    def test_gen_1_1(self):
        d = self.books["Gen"]["1"]["1"]
        self.assertTrue(nfc(d["w"]).startswith(nfc("ἐν ἀρχῇ ἐποίησεν ὁ θεὸς")))
        self.assertTrue(nfc(d["l"]).startswith(nfc("ἐν ἀρχή ποιέω ὁ θεός")))

    # --- doubles textes de Rahlfs (DECISIONS.md) : B dans Josh/Judg, A dans JoshA/JudgA

    def test_juges_b_et_a(self):
        self.assertIn("διὰ τοῦ κυρίου", self.books["Judg"]["1"]["1"]["w"])   # B
        self.assertIn("ἐν κυρίῳ", self.books["JudgA"]["1"]["1"]["w"])        # A
        n_a = sum(1 for _ in verses({"JudgA": self.books["JudgA"]}))
        self.assertEqual(n_a, 617)

    def test_josue_b_et_a(self):
        self.assertIn("Καιβαισελεηλ", self.books["Josh"]["15"]["21"]["w"])   # B
        self.assertIn("Καβσεηλ", self.books["JoshA"]["15"]["21"]["w"])       # A
        self.assertEqual(set(self.books["JoshA"]), {"15", "18", "19"})
        n_a = sum(1 for _ in verses({"JoshA": self.books["JoshA"]}))
        self.assertEqual(n_a, 95)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless((DATA / "syr").exists(), "data/syr absent : lancer data/export_peshitta_tf.py")
class TestPeshitta(FormatChecks, unittest.TestCase):
    """Export de la Peshitta (DECISIONS.md « Export de la Peshitta ») : pas de
    couche l (aucun lemme dans le corpus), un mot = un mot graphique."""
    layers = {"t", "w", "g"}

    @classmethod
    def setUpClass(cls):
        cls.aligned = load_dir(DATA / "syr")
        cls.books = {**cls.aligned, **load_dir(DATA / "syr" / "non_aligned")}

    def test_livres_hebreux(self):
        # mêmes noms de fichiers que la BHSA (data/he)
        he = {p.stem for p in (DATA / "he").glob("*.json")}
        self.assertLessEqual(set(self.aligned), he)

    def test_g_un_mot_par_token(self):
        for ref, d in verses(self.books):
            self.assertEqual(d["g"], " ".join(str(i) for i in range(len(d["w"].split(" ")))), ref)

    def test_ecriture_syriaque(self):
        for ref, d in verses(self.aligned):
            self.assertRegex(d["w"], r"[ܐ-ܯ]", ref)
