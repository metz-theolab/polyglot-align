"""Tests de la reprise d'une expérience interrompue et du non-écrasement des
résultats (align.py, experiment.py ; DECISIONS.md, étape 5 de « Paquet Python
installable… »).

Usage (depuis la racine du projet) : python -m unittest tests/test_resume.py -v
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from polyglot_align.align import align, done_records
from polyglot_align.aligners import Aligner, VerseAlignment
from polyglot_align.experiment import Experiment
from polyglot_align.store import DataStore

ROOT = Path(__file__).resolve().parent.parent
STORE = DataStore(ROOT / "data")
PAIRS = STORE.verse_pairs("Gen", "Gen", only="Gen.1")     # 31 versets


class Crash(Exception):
    pass


class DiagonalAligner(Aligner):
    """Relie le token i au token i ; s'arrête (Crash) au verset `crash_at`."""

    def __init__(self, crash_at=None):
        super().__init__()
        self.crash_at, self.seen = crash_at, []

    def align(self, hv, gv) -> VerseAlignment:
        if hv.ref == self.crash_at:
            raise Crash(hv.ref)
        self.seen.append(hv.ref)
        src, tgt = hv.tokens(), gv.tokens()
        return VerseAlignment(src, tgt, {"inter": [(i, i) for i in range(min(len(src), len(tgt)))]})


class TestAlignReprise(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.full = self.tmp / "complet.jsonl"
        align(DiagonalAligner(), PAIRS, self.full)       # exécution sans interruption
        self.path = self.tmp / "Gen.1.jsonl"

    def test_reprise_apres_arret(self):
        with self.assertRaises(Crash):
            align(DiagonalAligner(crash_at="Gen.1.6"), PAIRS, self.path)
        self.assertEqual(len(done_records(self.path)[0]), 5)       # Gen.1.1 à 1.5 sur disque
        a = DiagonalAligner()
        self.assertEqual(align(a, PAIRS, self.path), (26, 5))
        self.assertEqual(a.seen[0], "Gen.1.6")
        self.assertEqual(self.path.read_bytes(), self.full.read_bytes())

    def test_derniere_ligne_incomplete_refaite(self):
        data = self.full.read_bytes()
        lines = data.split(b"\n")
        self.path.write_bytes(b"\n".join(lines[:3]) + b"\n" + lines[3][:40])   # 3 versets + un reste
        with self.assertLogs("polyglot_align.align", "WARNING"):
            self.assertEqual(align(DiagonalAligner(), PAIRS, self.path), (28, 3))
        self.assertEqual(self.path.read_bytes(), data)

    def test_ligne_illisible_au_milieu(self):
        lines = self.full.read_text(encoding="utf-8").splitlines()
        lines[2] = lines[2][:40]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "ligne 3"):
            align(DiagonalAligner(), PAIRS, self.path)

    def test_passage_complet_rien_a_refaire(self):
        a = DiagonalAligner()
        self.assertEqual(align(a, PAIRS, self.full), (0, 31))
        self.assertEqual(a.seen, [])

    def test_versets_hors_du_passage(self):
        with self.assertRaisesRegex(ValueError, "hors du passage"):
            align(DiagonalAligner(), STORE.verse_pairs("Gen", "Gen", only="Gen.2"), self.full)


class TestExperienceReprise(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.config = self.tmp / "e.yaml"
        self.write_config(hebrew="unvocalized")

    def write_config(self, **options):
        self.config.write_text(yaml.safe_dump({
            "name": "e", "passages": [{"book": "Gen", "only": "Gen.1"}],
            "aligner": {"type": "eflomal"}, **options}), encoding="utf-8")

    def run_experiment(self, aligner, **kwargs):
        exp = Experiment.from_yaml(self.config, results_root=self.tmp / "results",
                                   data_root=ROOT / "data", **kwargs)
        return exp, exp.run(aligner=aligner)

    def test_reprise_meme_config(self):
        with self.assertRaises(Crash):
            self.run_experiment(DiagonalAligner(crash_at="Gen.1.10"))
        exp, scores = self.run_experiment(DiagonalAligner())
        self.assertEqual((exp.n_verses, exp.n_resumed), (22, 9))
        _, ref = self.run_experiment(DiagonalAligner(), force=True)   # de zéro, sans arrêt
        self.assertEqual(scores, ref)

    def test_autre_config_refusee(self):
        self.run_experiment(DiagonalAligner())
        self.write_config(hebrew="vocalized")
        with self.assertRaisesRegex(ValueError, "autre config.*hebrew"):
            self.run_experiment(DiagonalAligner())

    def test_force_repart_de_zero(self):
        self.run_experiment(DiagonalAligner())
        self.write_config(hebrew="vocalized")
        exp, _ = self.run_experiment(DiagonalAligner(), force=True)
        self.assertEqual((exp.n_verses, exp.n_resumed), (31, 0))
        copied = yaml.safe_load((self.tmp / "results" / "e" / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(copied["hebrew"], "vocalized")


if __name__ == "__main__":
    unittest.main()
