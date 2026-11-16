"""Tests de l'API (client de test FastAPI), sans modèle : les aligneurs de
textes sont simulés (segmentation par une petite table, liens token i ↔
token i), un par algorithme.

Usage (depuis la racine du dépôt) : python -m unittest discover -s app/backend/tests
"""
import os
import threading
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from polyglot_align.segment import TableSegmenter, greek_verse, hebrew_verse
from polyglot_align.textalign import TextAlignment
from polyglot_api.main import create_app
from polyglot_api.services.aligner import AlignerService
from polyglot_api.settings import Settings

HEBREW = "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
GREEK = "ἐν ἀρχῇ ἐποίησεν ὁ θεός"

METHODS = {"eflomal": {"sure": "inter", "all": "gdfa"},
           "simalign": {"sure": "inter (argmax)", "all": "itermax"},
           "llm": {"sure": "gemma4:12b", "all": "gemma4:12b"}}


class FakeTextAligner:
    """Même interface que les aligneurs de polyglot_align.textalign."""
    hebrew, greek = "unvocalized", "unaccented"

    def __init__(self, base, name):
        self.segmenter, self.name, self.calls = base["segmenter"], name, 0

    def align_many(self, pairs):
        self.calls += 1
        out = []
        for k, (he, gr) in enumerate(pairs, 1):
            hv, gv = hebrew_verse(he, self.segmenter, f"A.1.{k}"), greek_verse(gr, f"B.1.{k}")
            n = min(len(hv.tokens("w")), len(gv.tokens("w")))
            sure = [(i, i) for i in range(n)]
            probable = [] if self.name == "llm" else [(n - 1, n)]
            out.append(TextAlignment(hv, gv, {"sure": sure, "all": sorted(set(sure) | set(probable))},
                                     self.name, METHODS[self.name]))
        return out


def base():
    return {"segmenter": TableSegmenter().fit([("בראשית", ("ב", "ראשית")), ("ברא", ("ברא",)),
                                               ("אלהים", ("אלהים",))])}


def service(llm_reason=None, load=True):
    """Service simulé : eflomal, simalign, llm ; llm_reason : LLM indisponible."""
    reason = [llm_reason]
    s = AlignerService(base, {n: (lambda b, n=n: FakeTextAligner(b, n)) for n in METHODS},
                       checks={"llm": lambda: reason[0]})
    s.llm_reason = reason          # pour changer la disponibilité pendant un test
    if load:
        s.load()
    return s


def client(svc=None, **settings) -> TestClient:
    return TestClient(create_app(Settings(load_on_startup=False, **settings), svc or service()))


class TestEtat(unittest.TestCase):
    def test_pret(self):
        r = client().get("/api/v1/health")
        self.assertEqual((r.status_code, r.json()["status"]), (200, "ready"))

    def test_en_chargement(self):
        c = client(service(load=False))
        r = c.get("/api/v1/health")
        self.assertEqual((r.status_code, r.json()["status"]), (503, "loading"))
        r = c.post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK})
        self.assertEqual((r.status_code, r.headers["retry-after"]), (503, "10"))

    def test_chargement_en_erreur(self):
        def broken():
            raise FileNotFoundError("data/verse_map.json")
        s = AlignerService(broken, {"eflomal": lambda b: None})
        s.load()
        r = client(s).get("/api/v1/health")
        self.assertEqual((r.status_code, r.json()["status"]), (503, "error"))
        self.assertIn("verse_map", r.json()["detail"])

    def test_info_liste_des_algorithmes(self):
        d = client(service(llm_reason="Ollama not reachable")).get("/api/v1/info").json()
        self.assertEqual(d["default"], "eflomal")
        algos = {a["name"]: a for a in d["algorithms"]}
        self.assertEqual([a["name"] for a in d["algorithms"]], ["eflomal", "simalign", "llm"])
        self.assertEqual((algos["eflomal"]["status"], algos["simalign"]["status"]), ("ready", "ready"))
        self.assertEqual((algos["llm"]["status"], algos["llm"]["detail"]),
                         ("unavailable", "Ollama not reachable"))
        self.assertIn("glot500", algos["simalign"]["label"].lower())

    def test_llm_disponible_apres_coup(self):
        """Ollama démarré après l'API : /info revérifie, le LLM devient prêt."""
        s = service(llm_reason="Ollama not reachable")
        c = client(s)
        body = {"hebrew": HEBREW, "greek": GREEK, "algorithm": "llm"}
        self.assertEqual(c.post("/api/v1/align", json=body).status_code, 503)
        s.llm_reason[0] = None
        algos = {a["name"]: a["status"] for a in c.get("/api/v1/info").json()["algorithms"]}
        self.assertEqual(algos["llm"], "ready")
        self.assertEqual(c.post("/api/v1/align", json=body).status_code, 200)

    def test_documentation(self):
        self.assertEqual(client().get("/openapi.json").status_code, 200)


class TestAlignement(unittest.TestCase):
    def test_align_par_defaut_eflomal(self):
        r = client().post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["hebrew"]["tokens"], ["בְּ", "רֵאשִׁית", "בָּרָא", "אֱלֹהִים"])
        self.assertEqual(d["hebrew"]["graphic"], [0, 0, 1, 2])
        self.assertEqual(d["greek"]["tokens"], ["ἐν", "ἀρχῇ", "ἐποίησεν", "ὁ", "θεός"])
        self.assertEqual(d["links"]["sure"][:2], [[0, 0], [1, 1]])
        self.assertTrue(set(map(tuple, d["links"]["sure"])) <= set(map(tuple, d["links"]["all"])))
        self.assertEqual((d["algorithm"], d["methods"]), ("eflomal", {"sure": "inter", "all": "gdfa"}))
        self.assertEqual(d["unknown_hebrew_words"], [])
        self.assertEqual((d["meta"]["algorithm"], d["meta"]["hebrew"]), ("eflomal", "unvocalized"))

    def test_choix_de_l_algorithme(self):
        c = client()
        for name in ("simalign", "llm"):
            d = c.post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK, "algorithm": name}).json()
            self.assertEqual((d["algorithm"], d["meta"]["algorithm"]), (name, name))
            self.assertEqual(d["methods"], METHODS[name])
        self.assertEqual(d["links"]["sure"], d["links"]["all"])        # llm : un seul niveau

    def test_algorithme_inconnu_422(self):
        r = client().post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK, "algorithm": "giza"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("unknown algorithm", r.json()["detail"])

    def test_algorithme_indisponible_503(self):
        r = client(service(llm_reason="Ollama not reachable at http://x")).post(
            "/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK, "algorithm": "llm"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("Ollama not reachable", r.json()["detail"])

    def test_mot_inconnu_signale(self):
        d = client().post("/api/v1/align", json={"hebrew": HEBREW + " וַיֹּאמֶר", "greek": GREEK}).json()
        self.assertEqual(d["unknown_hebrew_words"], ["ויאמר"])

    def test_texte_vide_422(self):
        r = client().post("/api/v1/align", json={"hebrew": "…", "greek": GREEK})
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "no Hebrew word in text A"))
        r = client().post("/api/v1/align", json={"hebrew": HEBREW, "greek": "123"})
        self.assertEqual((r.status_code, r.json()["detail"]), (422, "no Greek word in text B"))

    def test_texte_trop_long_413(self):
        r = client(max_chars=10).post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK})
        self.assertEqual(r.status_code, 413)

    def test_requete_mal_formee_422(self):
        self.assertEqual(client().post("/api/v1/align", json={"hebrew": HEBREW}).status_code, 422)

    def test_batch_un_seul_appel(self):
        s = service()
        pairs = [{"hebrew": HEBREW, "greek": GREEK}, {"hebrew": "אֱלֹהִים", "greek": "θεός"}]
        r = client(s).post("/api/v1/align/batch", json={"pairs": pairs})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 2)
        self.assertEqual(s.algorithms["eflomal"]["aligner"].calls, 1)

    def test_batch_trop_de_paires_413(self):
        pairs = [{"hebrew": HEBREW, "greek": GREEK}] * 3
        r = client(max_batch=2).post("/api/v1/align/batch", json={"pairs": pairs})
        self.assertEqual(r.status_code, 413)

    def test_segment(self):
        d = client().post("/api/v1/segment", json={"hebrew": "בְּרֵאשִׁית בָּרָא"}).json()
        self.assertEqual(d["hebrew"]["tokens"], ["בְּ", "רֵאשִׁית", "בָּרָא"])
        self.assertEqual(d["hebrew"]["graphic"], [0, 0, 1])


class TestServeur(unittest.TestCase):
    def test_cors_origine_autorisee_seulement(self):
        c = client(cors_origins=["http://localhost:5173"])
        ok = c.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "http://localhost:5173")
        other = c.get("/api/v1/health", headers={"Origin": "http://exemple.org"})
        self.assertNotIn("access-control-allow-origin", other.headers)

    def test_un_alignement_a_la_fois(self):
        """Requêtes simultanées, algorithmes différents : jamais deux alignements ensemble."""
        s = service()
        running, overlap = [0], []
        for a in s.algorithms.values():
            original = a["aligner"].align_many

            def slow(pairs, original=original):
                running[0] += 1
                overlap.append(running[0])
                threading.Event().wait(0.05)
                running[0] -= 1
                return original(pairs)
            a["aligner"].align_many = slow
        c = client(s)
        threads = [threading.Thread(target=c.post, args=("/api/v1/align",),
                                    kwargs={"json": {"hebrew": HEBREW, "greek": GREEK, "algorithm": n}})
                   for n in ("eflomal", "simalign", "llm")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual((len(overlap), max(overlap)), (3, 1))

    def test_reglages_par_variables_d_environnement(self):
        env = {"POLYGLOT_PORT": "9000", "POLYGLOT_HOST": "0.0.0.0",
               "POLYGLOT_CORS_ORIGINS": '["http://front:80"]', "POLYGLOT_DATA_DIR": "/srv/data",
               "POLYGLOT_ALGORITHMS": '["eflomal", "llm"]', "POLYGLOT_OLLAMA_URL": "http://ollama:11434"}
        with mock.patch.dict(os.environ, env):
            s = Settings()
        self.assertEqual((s.port, s.host, s.cors_origins, str(s.data_dir)),
                         (9000, "0.0.0.0", ["http://front:80"], "/srv/data"))
        self.assertEqual((s.algorithms, s.ollama_url), (["eflomal", "llm"], "http://ollama:11434"))


if __name__ == "__main__":
    unittest.main()
