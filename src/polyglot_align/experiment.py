"""Une expérience : aligner puis évaluer les passages décrits dans une Config.

Écrit dans results/<name>/ :
    config.yaml        copie de la configuration utilisée
    <passage>.jsonl    alignements (relire avec polyglot-align show)
    <passage>.csv      relecture : un mot hébreu par ligne, avec le verdict du gold
    scores.json        comptes bruts et mesures, par passage et au total
    scores.csv         le tableau des mesures
    perf.json          durée, temps CPU, mémoire et débit, par phase (voir perf.py)

Reprise : relancer une expérience interrompue saute les versets déjà alignés
(align.py). Un dossier de résultats produit par une autre config n'est pas
écrasé, sauf avec force=True (--force), qui repart de zéro.
"""
import csv
import json
import logging
import shutil
from collections import Counter
from pathlib import Path

import yaml

from polyglot_align.align import align
from polyglot_align.aligners import make_aligner
from polyglot_align.config import Config
from polyglot_align.evaluation.evaluate import Evaluator, measures
from polyglot_align.perf import PerfMeter
from polyglot_align.store import DataStore

log = logging.getLogger(__name__)

# fichiers écrits par une expérience (effacés par force=True)
OUTPUTS = ["*.jsonl", "*.csv", "scores.json", "perf.json", "config.yaml"]

COLUMNS = ["precision", "rappel_blocs", "f1", "nonalign_exactitude", "aer",
           "couverture_hb", "couverture_gr"]


class Experiment:
    def __init__(self, cfg: Config, config_path=None, results_root="results", data_root="data",
                 force: bool = False):
        self.cfg = cfg
        self.config_path = config_path   # copié dans le dossier des résultats
        self.force = force               # repartir de zéro (efface les résultats précédents)
        self.store = DataStore(data_root)   # textes, gold, table des versets (data/)
        self.out = Path(results_root) / cfg.name
        self.scores = {}                 # passage -> résultats ; puis "TOTAL"
        self.perf = PerfMeter()          # durées par phase -> perf.json
        self.n_verses = 0                # versets alignés pendant cette exécution
        self.n_resumed = 0               # versets repris d'une exécution précédente

    @classmethod
    def from_yaml(cls, path, **kwargs) -> "Experiment":
        return cls(Config.from_yaml(path), config_path=path, **kwargs)

    def run(self, aligner=None) -> dict:
        """Lance toute l'expérience et renvoie les scores.
        aligner : par défaut, construit d'après la config (SimAlign ou LLM) ;
        un autre Aligner peut être fourni (tests)."""
        self.prepare()
        with self.perf.phase("chargement"):
            aligner = aligner or make_aligner(self.cfg)
        with self.perf.phase("apprentissage"):
            aligner.fit(self.training_pairs())
        for p in self.cfg.passages:
            n, resumed = self.run_passage(aligner, p)
            self.n_verses += n
            self.n_resumed += resumed
            if resumed:
                log.info("%s : %d versets alignés (%d repris), évalués", p.label, n, resumed)
            else:
                log.info("%s : %d versets alignés et évalués", p.label, n)
        if aligner.stats:
            log.info("%s : %s", type(aligner).__name__, dict(aligner.stats))
        self.scores["TOTAL"] = self.total()
        self.write_scores()
        self.write_perf(aligner)
        self.log_table()
        return self.scores

    def training_pairs(self):
        """Paires de versets données à Aligner.fit : toute la table des versets
        (seul endroit où se décidera le découpage entraînement / test)."""
        return self.store.table_pairs()

    def prepare(self) -> None:
        """Crée le dossier des résultats et y copie la configuration. Refuse un
        dossier produit par une autre config ; force=True l'efface d'abord."""
        previous = self.out / "config.yaml"
        if self.force:
            self.clear()
        elif previous.exists():
            diff = self.cfg.differences(Config.from_yaml(previous))
            if diff:
                raise ValueError(f"{self.out}/ contient les résultats d'une autre config "
                                 f"(options différentes : {', '.join(diff)}) ; changer `name` "
                                 "ou relancer avec --force pour repartir de zéro")
        self.out.mkdir(parents=True, exist_ok=True)
        if self.config_path:
            shutil.copy(self.config_path, previous)
        else:
            previous.write_text(yaml.safe_dump(self.cfg.to_dict(), allow_unicode=True, sort_keys=False),
                                encoding="utf-8")

    def clear(self) -> None:
        """Efface les sorties d'une exécution précédente (seulement les fichiers
        qu'écrit une expérience, voir OUTPUTS)."""
        for pattern in OUTPUTS:
            for f in self.out.glob(pattern):
                f.unlink()
                log.info("effacé : %s", f)

    def run_passage(self, aligner, p) -> int:
        """Aligne, évalue et écrit le CSV de relecture d'un passage.
        Renvoie (versets alignés pendant cette exécution, versets repris)."""
        jsonl = self.out / f"{p.label}.jsonl"
        with self.perf.phase("alignement"):
            n, resumed = align(aligner, self.store.verse_pairs(p.book, p.lxx_book, p.only), jsonl)
        with self.perf.phase("evaluation"):
            evaluator = Evaluator.from_store(self.store, p.book, p.lxx_book, layer=self.cfg.tokens)
            self.scores[p.label] = evaluator.evaluate(jsonl)
            evaluator.export_csv(jsonl, self.out / f"{p.label}.csv")
        return n, resumed

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

    def write_perf(self, aligner) -> None:
        """Écrit perf.json et en donne le résumé dans le journal."""
        comptes = next(iter(self.scores["TOTAL"]["methodes"].values()), {}).get("comptes", {})
        perf = self.perf.report(self.n_verses, comptes.get("tokens_hb", 0), comptes.get("tokens_gr", 0),
                                device=self.cfg.aligner.get("device"),
                                aligner_stats=dict(aligner.stats), versets_repris=self.n_resumed)
        (self.out / "perf.json").write_text(json.dumps(perf, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
        c, d = perf["cout_methode"], perf["debit_alignement"]
        log.info(f"\nPerformances : {c['duree_s']:.1f} s (apprentissage + alignement), "
                 f"CPU {c['cpu_s']:.1f} s, {c['s_par_1000_versets']} s / 1000 versets, "
                 f"{d['versets_par_s']} versets/s, mémoire max {perf['memoire_max_mo']} Mo")

    def log_table(self) -> None:
        """Tableau des mesures, dans le journal."""
        log.info(f"\nRésultats dans {self.out}/")
        pct = lambda v: f"{v:.1%}" if v is not None else "—"
        log.info(f"{'passage':<10} {'méthode':<8} {'préc.':>6} {'rappel':>7} {'F1':>6} {'non-al.':>8} {'AER':>6}")
        for label, m, x in self.rows():
            log.info(f"{label:<10} {m:<8} {pct(x['precision']):>6} {pct(x['rappel_blocs']):>7} "
                     f"{pct(x['f1']):>6} {pct(x['nonalign_exactitude']):>8} {pct(x['aer']):>6}")
