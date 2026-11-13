"""Une expérience : aligner puis évaluer les passages décrits dans une Config.

Écrit dans results/<name>/ :
    config.yaml        copie de la configuration utilisée
    <passage>.jsonl    alignements (relire avec src/show.py)
    <passage>.csv      relecture : un mot hébreu par ligne, avec le verdict du gold
    scores.json        comptes bruts et mesures, par passage et au total
    scores.csv         le tableau des mesures
"""
import csv
import json
import shutil
from collections import Counter
from pathlib import Path

from align import align
from aligners import make_aligner
from config import Config
from evaluate import Evaluator, measures

COLUMNS = ["precision", "rappel_blocs", "f1", "nonalign_exactitude", "aer",
           "couverture_hb", "couverture_gr"]


class Experiment:
    def __init__(self, cfg: Config, config_path=None, results_root="results", data_root="data"):
        self.cfg = cfg
        self.config_path = config_path   # copié dans le dossier des résultats
        self.data = Path(data_root)
        self.out = Path(results_root) / cfg.name
        self.scores = {}                 # passage -> résultats ; puis "TOTAL"

    @classmethod
    def from_yaml(cls, path, **kwargs) -> "Experiment":
        return cls(Config.from_yaml(path), config_path=path, **kwargs)

    def run(self, aligner=None) -> dict:
        """Lance toute l'expérience et renvoie les scores.
        aligner : par défaut, construit d'après la config (SimAlign ou LLM) ;
        un autre Aligner peut être fourni (tests)."""
        self.prepare()
        aligner = aligner or make_aligner(self.cfg)
        for p in self.cfg.passages:
            n = self.run_passage(aligner, p)
            print(f"{p.label} : {n} versets alignés et évalués")
        if aligner.stats:
            print(f"{type(aligner).__name__} :", dict(aligner.stats))
        self.scores["TOTAL"] = self.total()
        self.write_scores()
        self.print_table()
        return self.scores

    def prepare(self) -> None:
        """Crée le dossier des résultats et y copie la configuration."""
        self.out.mkdir(parents=True, exist_ok=True)
        if self.config_path:
            shutil.copy(self.config_path, self.out / "config.yaml")

    def run_passage(self, aligner, p) -> int:
        """Aligne, évalue et écrit le CSV de relecture d'un passage.
        Renvoie le nombre de versets alignés."""
        jsonl = self.out / f"{p.label}.jsonl"
        n = align(aligner, self.data / "he" / f"{p.book}.json",
                  self.data / "lxx" / f"{p.lxx_book}.json", jsonl, p.only)
        evaluator = Evaluator.for_books(p.book, p.lxx_book, root=self.data, layer=self.cfg.tokens)
        self.scores[p.label] = evaluator.evaluate(jsonl)
        evaluator.export_csv(jsonl, self.out / f"{p.label}.csv")
        return n

    def total(self) -> dict:
        """Somme des comptes de tous les passages, par méthode (moyenne micro)."""
        sums = {}
        for res in self.scores.values():
            for m, r in res["methodes"].items():
                sums.setdefault(m, Counter()).update(r["comptes"])
        return {"methodes": {m: {"mesures": measures(c), "comptes": dict(c)} for m, c in sums.items()}}

    def rows(self):
        """(passage, méthode, mesures), total compris, dans l'ordre d'affichage."""
        for label, res in self.scores.items():
            for m, r in res["methodes"].items():
                yield label, m, r["mesures"]

    def write_scores(self) -> None:
        (self.out / "scores.json").write_text(json.dumps(self.scores, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        with open(self.out / "scores.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["passage", "methode"] + COLUMNS)
            for label, m, x in self.rows():
                w.writerow([label, m] + [x[c] for c in COLUMNS])

    def print_table(self) -> None:
        print(f"\nRésultats dans {self.out}/")
        pct = lambda v: f"{v:.1%}" if v is not None else "—"
        print(f"{'passage':<10} {'méthode':<8} {'préc.':>6} {'rappel':>7} {'F1':>6} {'non-al.':>8} {'AER':>6}")
        for label, m, x in self.rows():
            print(f"{label:<10} {m:<8} {pct(x['precision']):>6} {pct(x['rappel_blocs']):>7} "
                  f"{pct(x['f1']):>6} {pct(x['nonalign_exactitude']):>8} {pct(x['aer']):>6}")
