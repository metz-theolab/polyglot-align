"""Tests du lecteur des textes alignés (/api/v1/reader), sur de petits
résultats fabriqués dans un dossier temporaire (pas de results/ réel).

Usage (depuis la racine du dépôt) : python -m unittest discover -s app/backend/tests
"""
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from polyglot_align.store import DataStore
from polyglot_api.main import create_app
from polyglot_api.services.aligner import AlignerService
from polyglot_api.services.reader import Reader
from polyglot_api.settings import Settings

# Gn 1,1 réduit : 3 mots séparés par des espaces, dont un avec maqqef (2 mots graphiques)
HE = {"Gen": {"1": {
    "1": {"t": "בְּרֵאשִׁית בָּרָא אֶת־הַשָּׁמַיִם׃ ס", "w": "בְּ רֵאשִׁית בָּרָא אֶת הַ שָּׁמַיִם",
          "l": "ב ראשית ברא את ה שמים", "g": "0 0 1 2 3 3"},
    "2": {"t": "וְהָאָרֶץ", "w": "וְ הָ אָרֶץ", "l": "ו ה ארץ", "g": "0 0 0"}}}}
LXX = {"Gen": {"1": {"1": {"t": "ἐν ἀρχῇ ἐποίησεν τὸν οὐρανόν", "w": "ἐν ἀρχῇ ἐποίησεν τὸν οὐρανόν",
                           "l": "ἐν ἀρχή ποιέω ὁ οὐρανός", "g": "0 1 2 3 4"}}}}
SYR = {"Gen": {"1": {"1": {"t": "ܒܪܫܝܬ ܒܪܐ ܝܬ ܫܡܝܐ.", "w": "ܒܪܫܝܬ ܒܪܐ ܝܬ ܫܡܝܐ", "g": "0 1 2 3"},
                     "2": {"t": "ܘܐܪܥܐ", "w": "ܘܐܪܥܐ", "g": "0"}}}}

# LXX : tokens w (6 tokens hébreux) ; Peshitta : tokens t (4 tokens, ס compris)
LXX_LINE = {"ref": "Gen.1.1", "src": ["ב", "ראשית", "ברא", "את", "ה", "שמים"],
            "tgt": ["εν", "αρχη", "εποιησεν", "τον", "ουρανον"],
            "links": {"inter": "0-0", "gdfa": "0-0 1-1 2-2 3-3 5-4"}}
SYR_LINES = [{"ref": "Gen.1.1", "src": ["בְּרֵאשִׁית", "בָּרָא", "אֶת־הַשָּׁמַיִם", "ס"],
              "tgt": ["ܒܪܫܝܬ", "ܒܪܐ", "ܝܬ", "ܫܡܝܐ"],
              "links": {"inter": "0-0", "gdfa": "0-0 1-1 2-2 2-3"}},
             {"ref": "Gen.1.2", "src": ["וְהָאָרֶץ"], "tgt": ["ܘܐܪܥܐ"], "links": {"gdfa": "0-0"}}]
CSV = ("﻿ref;methode;n;hebreu;grec_aligne;bloc_catss;catss_hebreu;catss_grec;verdict\n"
       + "".join(f"Gen.1.1;gdfa;{n};x;;;;;{v}\n"
                 for n, v in enumerate(["juste", "juste", "juste", "juste", "?", "faux"])))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestReader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        for side, data in (("he", HE), ("lxx", LXX), ("syr", SYR)):
            write(root / "data" / side / "Gen.json", json.dumps(data, ensure_ascii=False))
        res = root / "results"
        # ancien format plat (comme eflomal_unvocalized)
        write(res / "lxx_run" / "config.yaml", "name: lxx_run\npassages: [{book: Gen}]\n"
              "aligner: eflomal\ntokens: w\nhebrew_vocalization: false\n")
        write(res / "lxx_run" / "Gen.jsonl", json.dumps(LXX_LINE, ensure_ascii=False) + "\n")
        write(res / "lxx_run" / "Gen.csv", CSV)
        write(res / "syr_run" / "config.yaml", "name: syr_run\npassages: [{book: Gen}]\n"
              "target: syr\ntokens: t\nhebrew: pointed\naligner: {type: eflomal}\n")
        write(res / "syr_run" / "Gen.jsonl",
              "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in SYR_LINES))
        reader = Reader(DataStore(root / "data"), res, ["lxx_run", "syr_run", "absent"])
        svc = AlignerService(lambda: {}, {"eflomal": lambda b: None})
        cls.client = TestClient(create_app(Settings(load_on_startup=False), svc, reader))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def get(self, url):
        return self.client.get("/api/v1/reader" + url)

    def test_corpora_publies_seulement(self):
        r = self.get("/corpora").json()
        self.assertEqual([(c["id"], c["target"], c["direction"], c["gold"]) for c in r],
                         [("lxx_run", "lxx", "ltr", True), ("syr_run", "syr", "rtl", False)])

    def test_livres(self):
        r = self.get("/books").json()
        self.assertEqual(r, [{"book": "Gen", "chapters": ["1"],
                              "texts": [{"corpus": "lxx_run", "text": "Gen"},
                                        {"corpus": "syr_run", "text": "Gen"}]}])

    def test_chapitre_trilingue(self):
        v1, v2 = self.get("/Gen/1").json()["verses"]
        self.assertEqual([w["text"] for w in v1["words"]],
                         ["בְּרֵאשִׁית", "בָּרָא", "אֶת־הַשָּׁמַיִם׃", "ס"])
        self.assertEqual([w["graphic"] for w in v1["words"]], [True, True, True, False])
        lxx, syr = v1["targets"]
        # tokens du corpus (accentués) ; liens rattachés aux mots pivots : ב, ראשית -> 0 ; את, שמים -> 2
        self.assertEqual(lxx["tokens"], ["ἐν", "ἀρχῇ", "ἐποίησεν", "τὸν", "οὐρανόν"])
        self.assertEqual(lxx["links"], [[0, 0], [0, 1], [1, 2], [2, 3], [2, 4]])
        self.assertEqual(lxx["verdicts"], ["juste", "juste", "faux", None])  # pire de את, ה, שמים
        self.assertEqual(syr["tokens"], ["ܒܪܫܝܬ", "ܒܪܐ", "ܝܬ", "ܫܡܝܐ."])
        self.assertEqual(syr["links"], [[0, 0], [1, 1], [2, 2], [2, 3]])
        self.assertIsNone(syr["verdicts"])
        # Gn 1,2 : pas de LXX dans les résultats -> une seule cible
        self.assertEqual([t["corpus"] for t in v2["targets"]], ["syr_run"])

    def test_choix_des_corpus(self):
        v1 = self.get("/Gen/1?corpus=syr_run").json()["verses"][0]
        self.assertEqual([t["corpus"] for t in v1["targets"]], ["syr_run"])
        self.assertEqual(self.get("/Gen/1?corpus=zz").status_code, 422)

    def test_inconnus_404(self):
        self.assertEqual(self.get("/Exod/1").status_code, 404)
        self.assertEqual(self.get("/Gen/9").status_code, 404)
        self.assertEqual(self.get("/..%2Fhe%2FGen/1").status_code, 404)


if __name__ == "__main__":
    unittest.main()
