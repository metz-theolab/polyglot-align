"""Tests de la démo hébreu ↔ Peshitta (DECISIONS.md, FEAT / Syriaque) :
option target: syr, appariement par même référence, expérience sans gold.

Usage (depuis la racine du projet) : python -m unittest tests/test_syriac.py -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from polyglot_align.aligners import Aligner, VerseAlignment, make_aligner
from polyglot_align.config import Config, Passage
from polyglot_align.experiment import Experiment
from polyglot_align.normalize import norm_syr
from polyglot_align.store import DataStore

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HAS_SYR = (DATA / "syr" / "Gen.json").exists()


def syr_config(check=False, **kw):
    """Config de la démo (options complétées comme depuis un YAML)."""
    raw = {"name": "t", "passages": [{"book": "Gen", "only": "Gen.1"}], "target": "syr",
           "tokens": "t", "aligner": {"type": "eflomal"}} | kw
    return Config.from_dict(raw, check=check)


class TestConfig(unittest.TestCase):
    def test_syr_valide(self):
        syr_config().check()

    def test_syr_exige_t_et_eflomal(self):
        with self.assertRaises(ValueError):
            syr_config(tokens="g").check()
        with self.assertRaises(ValueError):
            syr_config(aligner={"type": "simalign"}).check()

    def test_t_refuse_avec_lxx(self):
        with self.assertRaises(ValueError):
            syr_config(target="lxx").check()

    def test_lxx_inchange(self):
        # target absent de to_dict par défaut : configs et résultats existants identiques
        cfg = Config(name="t", passages=[Passage("Gen")])
        self.assertNotIn("target", cfg.to_dict())
        self.assertIn("target", syr_config().to_dict())


class TestNormalisation(unittest.TestCase):
    def test_ponctuation_retiree(self):
        self.assertEqual(norm_syr("ܐܠܗܐ."), "ܐܠܗܐ")
        self.assertEqual(norm_syr("ܘܡܨܪܝܡ·"), "ܘܡܨܪܝܡ")

    def test_token_de_ponctuation_garde(self):
        self.assertEqual(norm_syr("•"), "•")      # jamais de token vide

    def test_syame_garde(self):
        self.assertIn("̈", norm_syr("ܫ̈ܡܝܐ"))


@unittest.skipUnless(HAS_SYR, "data/syr absent : lancer data/export_peshitta_tf.py")
class TestDonnees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = DataStore(DATA)

    def test_paires_meme_reference(self):
        pairs = self.store.target_pairs("syr", "Gen", "Gen", "Gen.1")
        self.assertEqual(len(pairs), 31)
        self.assertTrue(all(hv.key == sv.key for hv, sv in pairs))

    def test_corpus_entier(self):
        self.assertEqual(sum(1 for _ in self.store.training_pairs("syr")), 23006)

    def test_tokens_t(self):
        hv, sv = self.store.target_pairs("syr", "Gen", "Gen", "Gen.1.1")[0]
        a = make_aligner(syr_config())
        src, tgt = a.normalized_tokens(hv, sv)
        self.assertEqual(len(src), 7)                 # mots séparés par des espaces
        self.assertFalse(src[-1].endswith("׃"))      # sof pasuq retiré
        self.assertEqual(tgt[2], "ܐܠܗܐ")              # point retiré


class Diagonal(Aligner):
    """Faux aligneur : i ↔ i, pour tester l'expérience sans eflomal."""
    name = "diag"

    def align(self, hv, gv):
        src, tgt = self.normalized_tokens(hv, gv)
        return VerseAlignment(src, tgt, {"inter": [(i, i) for i in range(min(len(src), len(tgt)))]})


@unittest.skipUnless(HAS_SYR, "data/syr absent : lancer data/export_peshitta_tf.py")
class TestExperience(unittest.TestCase):
    def test_sans_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = Experiment(syr_config(name="demo"), results_root=tmp, data_root=DATA)
            exp.training_pairs = lambda: []           # pas d'apprentissage (faux aligneur)
            scores = exp.run(aligner=Diagonal(layer="t", hebrew="pointed", target="syr"))
            out = Path(tmp) / "demo"
            c = scores["TOTAL"]["methodes"]["inter"]
            self.assertEqual(c["comptes"]["versets"], 31)
            self.assertIsNone(c["mesures"]["precision"])
            lines = (out / "Gen.1.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["ref"], "Gen.1.1")
            self.assertIn("aligne", (out / "Gen.1.csv").read_text(encoding="utf-8-sig").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
