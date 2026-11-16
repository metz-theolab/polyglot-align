"""Tests de l'API (client de test FastAPI), sans modèle : le TextAligner est
remplacé par un aligneur simulé (segmentation par une petite table, liens
token i ↔ token i).

Usage (depuis la racine du dépôt) : python -m unittest discover -s app/backend/tests
"""
import threading
import unittest

from fastapi.testclient import TestClient

from polyglot_align.segment import TableSegmenter, greek_verse, hebrew_verse
from polyglot_align.textalign import TextAlignment
from polyglot_api.main import create_app
from polyglot_api.services.aligner import AlignerService
from polyglot_api.settings import Settings

HEBREW = "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
GREEK = "ἐν ἀρχῇ ἐποίησεν ὁ θεός"


class FakeTextAligner:
    """Même interface que polyglot_align.textalign.TextAligner."""
    hebrew, greek = "unvocalized", "unaccented"

    def __init__(self):
        self.segmenter = TableSegmenter().fit([("בראשית", ("ב", "ראשית")), ("ברא", ("ברא",)),
                                               ("אלהים", ("אלהים",))])
        self.calls = 0

    def align_many(self, pairs):
        self.calls += 1
        out = []
        for k, (he, gr) in enumerate(pairs, 1):
            hv, gv = hebrew_verse(he, self.segmenter, f"A.1.{k}"), greek_verse(gr, f"B.1.{k}")
            if not hv.layers["w"] or not gv.layers["w"]:
                raise ValueError(f"paire {k} : texte vide")
            n = min(len(hv.tokens("w")), len(gv.tokens("w")))
            diag = [(i, i) for i in range(n)]
            out.append(TextAlignment(hv, gv, {"inter": diag, "gdfa": diag + [(n - 1, n)]}))
        return out


def client(ready=True, **settings) -> TestClient:
    service = AlignerService(FakeTextAligner)
    if ready:
        service.load()
    app = create_app(Settings(load_on_startup=False, **settings), service)
    return TestClient(app)


class TestEtat(unittest.TestCase):
    def test_pret(self):
        r = client().get("/api/v1/health")
        self.assertEqual((r.status_code, r.json()["status"]), (200, "ready"))

    def test_en_chargement(self):
        c = client(ready=False)
        r = c.get("/api/v1/health")
        self.assertEqual((r.status_code, r.json()["status"]), (503, "loading"))
        r = c.post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.headers["retry-after"], "10")

    def test_chargement_en_erreur(self):
        def broken():
            raise FileNotFoundError("data/verse_map.json")
        service = AlignerService(broken)
        service.load()
        r = TestClient(create_app(Settings(load_on_startup=False), service)).get("/api/v1/health")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["status"], "error")
        self.assertIn("verse_map", r.json()["detail"])

    def test_info(self):
        d = client().get("/api/v1/info").json()
        self.assertEqual((d["aligner"], d["tokens"], d["segmenter"]), ("eflomal", "w", "table"))
        self.assertTrue(d["limits"])

    def test_documentation(self):
        self.assertEqual(client().get("/openapi.json").status_code, 200)


class TestAlignement(unittest.TestCase):
    def test_align(self):
        r = client().post("/api/v1/align", json={"hebrew": HEBREW, "greek": GREEK})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["hebrew"]["tokens"], ["בְּ", "רֵאשִׁית", "בָּרָא", "אֱלֹהִים"])
        self.assertEqual(d["hebrew"]["graphic"], [0, 0, 1, 2])
        self.assertEqual(d["greek"]["tokens"], ["ἐν", "ἀρχῇ", "ἐποίησεν", "ὁ", "θεός"])
        self.assertEqual(d["links"]["inter"][:2], [[0, 0], [1, 1]])
        self.assertTrue(set(map(tuple, d["links"]["inter"])) <= set(map(tuple, d["links"]["gdfa"])))
        self.assertEqual(d["unknown_hebrew_words"], [])
        self.assertEqual((d["meta"]["aligner"], d["meta"]["hebrew"]), ("eflomal", "unvocalized"))

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

    def test_batch_un_seul_apprentissage(self):
        service = AlignerService(FakeTextAligner)
        service.load()
        c = TestClient(create_app(Settings(load_on_startup=False), service))
        r = c.post("/api/v1/align/batch", json={"pairs": [{"hebrew": HEBREW, "greek": GREEK},
                                                          {"hebrew": "אֱלֹהִים", "greek": "θεός"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["results"]), 2)
        self.assertEqual(service.aligner.calls, 1)

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
        """Deux requêtes simultanées : les apprentissages ne se chevauchent pas."""
        service = AlignerService(FakeTextAligner)
        service.load()
        running, overlap = [0], []
        original = service.aligner.align_many

        def slow(pairs):
            running[0] += 1
            overlap.append(running[0])
            threading.Event().wait(0.05)
            running[0] -= 1
            return original(pairs)
        service.aligner.align_many = slow
        c = TestClient(create_app(Settings(load_on_startup=False), service))
        threads = [threading.Thread(target=c.post, args=("/api/v1/align",),
                                    kwargs={"json": {"hebrew": HEBREW, "greek": GREEK}}) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(max(overlap), 1)

    def test_reglages_par_variables_d_environnement(self):
        import os
        from unittest import mock
        env = {"POLYGLOT_PORT": "9000", "POLYGLOT_HOST": "0.0.0.0",
               "POLYGLOT_CORS_ORIGINS": '["http://front:80"]', "POLYGLOT_DATA_DIR": "/srv/data"}
        with mock.patch.dict(os.environ, env):
            s = Settings()
        self.assertEqual((s.port, s.host, s.cors_origins, str(s.data_dir)),
                         (9000, "0.0.0.0", ["http://front:80"], "/srv/data"))


if __name__ == "__main__":
    unittest.main()
