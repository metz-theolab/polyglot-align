"""Tests du module de rapport (polyglot_align.report), sur des résultats fabriqués.

Usage (depuis la racine du projet) : python -m unittest tests/test_report.py -v
"""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.report import ExperimentResult, ResultGroup, Table


def counts(justes, faux, trouves, evaluables, versets):
    return {"justes": justes, "faux": faux, "blocs_trouves": trouves,
            "blocs_evaluables": evaluables, "versets": versets}


def write_result(root: Path, name: str, passages: dict, config: dict) -> None:
    """passages : {label: {méthode: comptes}} ; le TOTAL n'est pas utilisé par report."""
    d = root / "results" / name
    d.mkdir(parents=True)
    scores = {p: {"methodes": {m: {"comptes": c} for m, c in ms.items()}} for p, ms in passages.items()}
    scores["TOTAL"] = {"methodes": {m: {} for m in next(iter(passages.values()))}}
    (d / "scores.json").write_text(json.dumps(scores), encoding="utf-8")
    (d / "config.yaml").write_text(yaml.safe_dump({"name": name, **config}), encoding="utf-8")


class TestReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "experiments").mkdir()
        self.roots = (self.root / "results", self.root / "experiments")

    def tearDown(self):
        self.tmp.cleanup()

    def test_agregation_micro(self):
        # A : 9/10 justes ; B : 1/10 -> micro 10/20 = 50 % (la moyenne des % donnerait aussi 50 %,
        # donc on prend des tailles différentes : 9/10 et 10/90 -> micro 19/100)
        write_result(self.root, "x", {"A": {"inter": counts(9, 1, 1, 1, 1)},
                                      "B": {"inter": counts(10, 80, 1, 1, 1)}}, {})
        m = ResultGroup("x", *self.roots).measures("inter")
        self.assertAlmostEqual(m["precision"][0], 0.19)
        self.assertIsNone(m["precision"][1])

    def test_executions_multiples(self):
        write_result(self.root, "llm_run1", {"G": {"llm": counts(8, 2, 1, 1, 1)}}, {"aligner": "llm"})
        write_result(self.root, "llm_run2", {"G": {"llm": counts(6, 4, 1, 1, 1)}}, {"aligner": "llm"})
        g = ResultGroup("llm", *self.roots)
        self.assertEqual(len(g.runs), 2)
        mean, sd = g.measures(g.resolve_method("inter"))["precision"]
        self.assertAlmostEqual(mean, 0.7)
        self.assertAlmostEqual(sd, 0.1414, places=3)

    def test_config_differente_signalee(self):
        write_result(self.root, "e", {"G": {"inter": counts(1, 0, 1, 1, 1)}},
                     {"aligner": "eflomal", "hebrew_vocalization": True})
        (self.root / "experiments" / "e.yaml").write_text(
            yaml.safe_dump({"name": "e", "aligner": "eflomal", "hebrew_vocalization": False}))
        r = ExperimentResult("e", *self.roots)
        self.assertTrue(any("hebrew_vocalization" in w for w in r.warnings))
        self.assertIn("voyelles", r.label())   # libellé tiré des résultats

    def test_versets_differents_signales(self):
        write_result(self.root, "a", {"G1": {"inter": counts(1, 0, 1, 1, 31)},
                                      "G3": {"inter": counts(1, 0, 1, 1, 24)}}, {})
        write_result(self.root, "b", {"G3": {"llm": counts(1, 0, 1, 1, 24)}}, {"aligner": "llm"})
        t = Table({"title": "t", "experiments": ["a", "b"]}, *self.roots).build()
        self.assertTrue(t.warnings)
        t = Table({"title": "t", "experiments": ["a", "b"], "passages": ["G3"]}, *self.roots).build()
        self.assertFalse(t.warnings)

    def test_ecriture_tex_md_csv(self):
        write_result(self.root, "a", {"Gen": {"inter": counts(9, 1, 3, 4, 2)}}, {})
        t = Table({"title": "Par livre", "experiment": "a", "rows": "passages"}, *self.roots).build()
        t.write(self.root)
        tex = (self.root / "par_livre.tex").read_text()
        self.assertIn(r"\toprule", tex)
        self.assertIn("Gen & 90.0 & 75.0", tex)
        self.assertIn("| TOTAL | 90.0% |", (self.root / "par_livre.md").read_text())


if __name__ == "__main__":
    unittest.main()
