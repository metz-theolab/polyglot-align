"""Test de bout en bout de src/experiment.py, sans modèle.

Un aligneur de rejeu renvoie les liens enregistrés dans une référence
(tests/reference/<nom>/) ; l'expérience complète (alignement, évaluation,
total, écriture) doit réécrire exactement les mêmes scores et CSV.

Usage (depuis la racine du projet) : python -m unittest tests/test_experiment.py -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from aligners import Aligner, VerseAlignment  # noqa: E402
from evaluate import parse_links              # noqa: E402
from experiment import Experiment             # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
