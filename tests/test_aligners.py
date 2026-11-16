"""Tests de l'interface Aligner (polyglot_align.aligners).

Le LLM n'est pas appelé : sa réponse est simulée par un tableau fixe, pour que
le test soit rapide et reproductible. SimAlign n'est pas chargé ici (lourd) :
il est couvert par le test de non-régression (tests/check_non_regression.py).

Usage (depuis la racine du projet) : python -m unittest tests/test_aligners.py -v
"""
import io
import json
import socket
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from polyglot_align.aligners import Aligner, VerseAlignment, make_aligner
from polyglot_align.config import Config
from polyglot_align.corpus import Corpus
from polyglot_align.aligners.llm import OllamaAligner, complete_rows

ROOT = Path(__file__).resolve().parent.parent

TABLE_GN_1_1 = {"rows": [
    {"hebrew": "בְּרֵאשִׁ֖ית", "greek": "ἐν ἀρχῇ"},
    {"hebrew": "בָּרָ֣א", "greek": "ἐποίησεν"},
    {"hebrew": "אֱלֹהִ֑ים", "greek": "ὁ θεὸς"},
    {"hebrew": "אֵ֥ת", "greek": ""},
    {"hebrew": "הַשָּׁמַ֖יִם", "greek": "τὸν οὐρανὸν"},
    {"hebrew": "וְאֵ֥ת", "greek": "καὶ"},
    {"hebrew": "הָאָֽרֶץ", "greek": "τὴν γῆν"},
]}


# réponse prise dans une boucle de répétition, coupée par num_predict (cas de Gn 45:1)
LOOP = (json.dumps(TABLE_GN_1_1, ensure_ascii=False)[:-2]
        + ', {"hebrew": "ועלמ", "greek": ""}' * 50 + ', {"hebr')


class FakeOllama(OllamaAligner):
    """OllamaAligner dont la réponse est fixée d'avance ; answer peut être une
    exception à lever (délai dépassé, serveur injoignable)."""

    def __init__(self, answer, done_reason: str = "stop"):
        super().__init__("faux-modele")
        self.answer, self.done_reason, self.prompts = answer, done_reason, []

    def _ask(self, prompt: str) -> tuple[str, str]:
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer, self.done_reason


class FakeResponse(io.BytesIO):
    """Réponse HTTP d'Ollama, pour urlopen simulé."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


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

    def test_prompt_non_vocalise(self):
        a = FakeOllama(json.dumps(TABLE_GN_1_1))
        a.hebrew = "unvocalized"
        res = a.align(self.hv, self.gv)
        self.assertIn("בראשית ברא אלהים", a.prompts[0])
        self.assertTrue({(0, 0), (0, 1), (1, 0), (1, 1)} <= set(res.links["llm"]))

    def test_prompt_grec_sans_accents(self):
        a = FakeOllama(json.dumps(TABLE_GN_1_1))
        a.greek = "unaccented"
        res = a.align(self.hv, self.gv)
        self.assertIn("εν αρχη εποιησεν ο θεος", a.prompts[0])
        # les liens ne dépendent pas des accents (lettres comparées sans accents)
        self.assertTrue({(0, 0), (0, 1), (1, 0), (1, 1)} <= set(res.links["llm"]))

    def test_reponse_invalide(self):
        a = FakeOllama("ceci n'est pas du JSON")
        res = a.align(self.hv, self.gv)
        self.assertEqual(res.links, {"llm": []})
        self.assertEqual((a.stats["reponses_invalides"], a.stats["versets_sans_reponse"]), (2, 1))

    def test_reponse_tronquee_lignes_completes_gardees(self):
        a = FakeOllama(LOOP, done_reason="length")
        res = a.align(self.hv, self.gv)
        self.assertEqual(len(a.prompts), 1)                 # pas de nouvel essai
        self.assertEqual(a.stats["reponses_tronquees"], 1)
        self.assertEqual(a.stats["versets_sans_reponse"], 0)
        self.assertEqual(res.extra["llm_table"][:7], TABLE_GN_1_1["rows"])
        # la ligne inventée de la boucle ne donne aucun lien : mêmes liens que la réponse complète
        full = FakeOllama(json.dumps(TABLE_GN_1_1)).align(self.hv, self.gv)
        self.assertEqual(res.links, full.links)

    def test_delai_depasse_verset_sans_reponse(self):
        a = FakeOllama(TimeoutError("600 s"))
        res = a.align(self.hv, self.gv)
        self.assertEqual(res.links, {"llm": []})
        self.assertEqual((a.stats["delais_depasses"], a.stats["versets_sans_reponse"]), (1, 1))
        self.assertEqual(len(a.prompts), 1)

    def test_serveur_injoignable_arrete(self):
        a = FakeOllama(RuntimeError("Ollama injoignable"))
        with self.assertRaisesRegex(RuntimeError, "injoignable"):
            a.align(self.hv, self.gv)


class TestCompleteRows(unittest.TestCase):
    def test_coupe_au_milieu_d_une_ligne(self):
        self.assertEqual(complete_rows('{"rows": [{"hebrew": "a", "greek": "b"}, {"hebrew": "c", "gr'),
                         [{"hebrew": "a", "greek": "b"}])

    def test_indente(self):
        text = '{\n  "rows": [\n    {\n      "hebrew": "a",\n      "greek": "b"\n    },\n    {\n      "heb'
        self.assertEqual(complete_rows(text), [{"hebrew": "a", "greek": "b"}])

    def test_sans_tableau(self):
        self.assertEqual(complete_rows('{"ro'), [])
        self.assertEqual(complete_rows(""), [])

    def test_boucle(self):
        rows = complete_rows(LOOP)
        self.assertEqual(rows[:7], TABLE_GN_1_1["rows"])
        self.assertEqual(rows[7:], [{"hebrew": "ועלמ", "greek": ""}] * 50)


class TestRequeteOllama(unittest.TestCase):
    """_ask avec urlopen simulé (aucun serveur n'est appelé, sauf un port fermé)."""

    def answer(self, done_reason="stop", content='{"rows": []}'):
        return FakeResponse(json.dumps({"message": {"content": content}, "done_reason": done_reason,
                                        "eval_count": 7}).encode())

    def test_limite_envoyee(self):
        with mock.patch("urllib.request.urlopen", return_value=self.answer()) as urlopen:
            content, done = OllamaAligner("m")._ask("p")
        body = json.loads(urlopen.call_args[0][0].data)
        self.assertEqual(body["options"]["num_predict"], 4096)
        self.assertEqual((content, done), ('{"rows": []}', "stop"))

    def test_sans_limite(self):
        with mock.patch("urllib.request.urlopen", return_value=self.answer()) as urlopen:
            OllamaAligner("m", num_predict=None)._ask("p")
        self.assertNotIn("num_predict", json.loads(urlopen.call_args[0][0].data)["options"])

    def test_delai_depasse(self):
        for error in [socket.timeout("timed out"), urllib.error.URLError(TimeoutError())]:
            with mock.patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(TimeoutError):
                    OllamaAligner("m")._ask("p")

    def test_erreur_http(self):
        error = urllib.error.HTTPError("u", 404, "model not found", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "404"):
                OllamaAligner("m")._ask("p")

    def test_serveur_injoignable(self):
        # port 9 (discard) : rien n'écoute, connexion refusée
        with self.assertRaisesRegex(RuntimeError, "injoignable"):
            OllamaAligner("m", url="http://127.0.0.1:9")._ask("p")


class TestMakeAligner(unittest.TestCase):
    def test_llm(self):
        cfg = Config.from_dict({"name": "x", "passages": [{"book": "Gen"}], "tokens": "l",
                                "hebrew": "vocalized", "aligner": {"type": "llm", "model": "gemma4:12b"}})
        a = make_aligner(cfg)
        self.assertIsInstance(a, OllamaAligner)
        self.assertEqual((a.model, a.layer, a.hebrew, a.greek), ("gemma4:12b", "l", "vocalized", "accented"))


if __name__ == "__main__":
    unittest.main()
