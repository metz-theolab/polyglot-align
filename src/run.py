"""Lance une expérience : aligne puis évalue les passages décrits dans un YAML.

Usage (depuis la racine du projet) : python src/run.py config.yaml

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
import sys
from collections import Counter
from pathlib import Path

import yaml

from align import align, make_aligner
from llm_align import OllamaAligner
from evaluate import evaluate_book, export_csv, measures

COLUMNS = ["precision", "rappel_blocs", "f1", "nonalign_exactitude", "aer",
           "couverture_hb", "couverture_gr"]


def main(config_path: str):
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    out = Path("results") / cfg["name"]
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(config_path, out / "config.yaml")

    if cfg.get("aligner", "simalign") == "llm":
        aligner = OllamaAligner(cfg["llm_model"], cfg.get("llm_url", "http://localhost:11434"),
                                think=cfg.get("llm_think", False))
    else:
        aligner = make_aligner(cfg["model"], cfg["layer"], cfg["methods"], cfg["device"])

    scores, total = {}, {}
    for p in cfg["passages"]:
        he_book = p["book"]
        lxx_book = p.get("lxx_book", he_book)
        label = p.get("only") or lxx_book
        jsonl = out / f"{label}.jsonl"
        n = align(aligner, f"data/he/{he_book}.json", f"data/lxx/{lxx_book}.json", jsonl,
                  cfg["tokens"], p.get("only"), cfg.get("greek_accents", True))
        res = evaluate_book(jsonl, Path(f"data/he/{he_book}.json"),
                            Path(f"data/lxx/{lxx_book}.json"),
                            Path(f"data/gold_clean/{lxx_book}.json"))
        export_csv(jsonl, Path(f"data/he/{he_book}.json"), Path(f"data/lxx/{lxx_book}.json"),
                   Path(f"data/gold_clean/{lxx_book}.json"), out / f"{label}.csv")
        scores[label] = res
        for m, r in res["methodes"].items():
            total.setdefault(m, Counter()).update(r["comptes"])
        print(f"{label} : {n} versets alignés et évalués")

    if getattr(aligner, "stats", None):
        print("Aligneur LLM :", dict(aligner.stats))
    scores["TOTAL"] = {"methodes": {m: {"mesures": measures(c), "comptes": dict(c)}
                                    for m, c in total.items()}}
    (out / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(out / "scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["passage", "methode"] + COLUMNS)
        for label, res in scores.items():
            for m, r in res["methodes"].items():
                w.writerow([label, m] + [r["mesures"][c] for c in COLUMNS])

    print(f"\nRésultats dans {out}/")
    pct = lambda v: f"{v:.1%}" if v is not None else "—"
    print(f"{'passage':<10} {'méthode':<8} {'préc.':>6} {'rappel':>7} {'F1':>6} {'non-al.':>8} {'AER':>6}")
    for label, res in scores.items():
        for m, r in res["methodes"].items():
            x = r["mesures"]
            print(f"{label:<10} {m:<8} {pct(x['precision']):>6} {pct(x['rappel_blocs']):>7} "
                  f"{pct(x['f1']):>6} {pct(x['nonalign_exactitude']):>8} {pct(x['aer']):>6}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
