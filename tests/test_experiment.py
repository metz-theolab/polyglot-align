"""Test de bout en bout de polyglot_align.experiment, sans modèle.

Un aligneur de rejeu renvoie les liens enregistrés dans une référence
(tests/reference/<nom>/) ; l'expérience complète (alignement, évaluation,
total, écriture) doit réécrire exactement les mêmes scores et CSV.

Usage (depuis la racine du projet) : python -m unittest tests/test_experiment.py -v
"""
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.aligners import Aligner, VerseAlignment
from polyglot_align.evaluation.evaluate import parse_links
from polyglot_align.experiment import Experiment

REFERENCE = ROOT / "tests" / "reference" / "mbert_formes_sans_accents"


class ReplayAligner(Aligner):
    """Renvoie, pour chaque verset, l'alignement enregistré dans la référence."""

    def __init__(self, ref_dir: Path):
        super().__init__()
        self.saved = {}
        for jsonl in ref_dir.glob("*.jsonl"):
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                d = json.loads(line)
                self.saved[d["ref"]] = d

    def align(self, hv, gv) -> VerseAlignment:
        d = self.saved[hv.ref]
        return VerseAlignment(d["src"], d["tgt"], {m: parse_links(r) for m, r in d["links"].items()})


class TestExperiment(unittest.TestCase):
    def test_rejeu_de_bout_en_bout(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Experiment.from_yaml(REFERENCE / "config.yaml", results_root=tmp,
                                       data_root=ROOT / "data")
            scores = exp.run(aligner=ReplayAligner(REFERENCE))
            out = Path(tmp) / exp.cfg.name
            for name in ["scores.csv", "Gen.1.csv", "Gen.3.csv", "1Sam.9.csv",
                         "Gen.1.jsonl", "Gen.3.jsonl", "1Sam.9.jsonl"]:
                self.assertEqual((out / name).read_bytes(), (REFERENCE / name).read_bytes(), name)
            self.assertIn("TOTAL", scores)
            self.assertEqual(list(scores), ["Gen.1", "Gen.3", "1Sam.9", "TOTAL"])
            perf = json.loads((out / "perf.json").read_text(encoding="utf-8"))
            self.assertEqual(set(perf["phases"]),
                             {"chargement", "apprentissage", "alignement", "evaluation"})
            self.assertEqual(perf["volume"]["versets"], 82)
            self.assertGreater(perf["volume"]["tokens_hb"], 0)
            self.assertGreater(perf["memoire_max_mo"], 0)


if __name__ == "__main__":
    unittest.main()
