"""Test de non-régression de la restructuration (voir DECISIONS.md).

Deux contrôles, contre les références produites avant la restructuration
(tests/reference/<nom>/ : config, alignements JSONL, scores) :

1. Rejeu (toutes les expériences, sans relancer les modèles) : on réévalue
   les alignements de référence avec le code actuel, et pour le LLM on
   reconvertit d'abord ses tableaux (champ llm_table) en liens. Les liens, les
   scores et le CSV de relecture doivent être identiques. Teste tout notre code (conversion,
   projection sur le gold, mesures), rapidement.

2. Relance (SimAlign seulement) : si results/<nom>/ existe, ses fichiers
   doivent être identiques à la référence, octet par octet. Le LLM n'est pas
   comparé ainsi : il n'est pas déterministe, même à température 0 avec une
   graine fixe (constaté le 2026-11-13 sur Gn 3:6).

Usage (depuis la racine du projet) :
    python tests/check_non_regression.py
    (après restructuration, relancer d'abord les expériences SimAlign :
     polyglot-align run experiments/<nom>.yaml)
"""
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
from polyglot_align.alignment import format_links, read_jsonl
from polyglot_align.evaluation.evaluate import Evaluator
from polyglot_align.aligners.llm import table_to_links

REFERENCE = ROOT / "tests" / "reference"
RESULTS = ROOT / "results"


def replay(ref_dir: Path) -> list:
    """Rejoue l'évaluation (et la conversion LLM) sur les JSONL de référence."""
    cfg = yaml.safe_load((ref_dir / "config.yaml").read_text(encoding="utf-8"))
    ref_scores = json.loads((ref_dir / "scores.json").read_text(encoding="utf-8"))
    problems = []
    for p in cfg["passages"]:
        he_book = p["book"]
        lxx_book = p.get("lxx_book", he_book)
        label = p.get("only") or lxx_book
        jsonl = ref_dir / f"{label}.jsonl"
        records = list(read_jsonl(jsonl))
        if not records:
            problems.append(f"{label} : JSONL de référence vide (référence invalide)")
            continue

        # conversion tableau -> liens (LLM)
        for rec in records:
            if "llm_table" in rec.extra:
                links = table_to_links(rec.src, rec.tgt, rec.extra["llm_table"])
                if format_links(links) != format_links(rec.links["llm"]):
                    problems.append(f"{label} {rec.ref} : la conversion du tableau donne d'autres liens")

        # réévaluation
        evaluator = Evaluator.for_books(he_book, lxx_book, root=ROOT / "data")
        res = evaluator.evaluate(jsonl)

        # CSV de relecture régénéré depuis le JSONL de référence
        ref_csv = ref_dir / f"{label}.csv"
        if ref_csv.exists():
            with tempfile.TemporaryDirectory() as tmp:
                new_csv = Path(tmp) / "x.csv"
                evaluator.export_csv(jsonl, new_csv)
                if new_csv.read_bytes() != ref_csv.read_bytes():
                    problems.append(f"{label} : CSV de relecture différent")
        old = ref_scores[label]["methodes"]
        for m, r in res["methodes"].items():
            if r != old.get(m):
                problems.append(f"{label} {m} : scores différents\n"
                                f"      référence : {old.get(m, {}).get('mesures')}\n"
                                f"      nouveau   : {r['mesures']}")
    return problems


def rerun(ref_dir: Path) -> list:
    """Compare results/<nom>/ (relancé) à la référence, fichier par fichier."""
    new_dir = RESULTS / ref_dir.name
    if not new_dir.exists():
        return None  # pas relancé : rien à comparer
    problems = []
    for ref in sorted(list(ref_dir.glob("*.jsonl")) + list(ref_dir.glob("*.csv"))):
        new = new_dir / ref.name
        if not new.exists():
            problems.append(f"{ref.name} : absent")
            continue
        a, b = ref.read_text(encoding="utf-8").splitlines(), new.read_text(encoding="utf-8").splitlines()
        if a != b:
            k = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            problems.append(f"{ref.name} : diffère à la ligne {k + 1}")
    return problems


def main() -> int:
    failed = 0
    for ref_dir in sorted(p for p in REFERENCE.iterdir() if p.is_dir()):
        is_llm = "llm_table" in next(ref_dir.glob("*.jsonl")).read_text(encoding="utf-8")
        problems = replay(ref_dir)
        status = "OK   " if not problems else "ÉCHEC"
        print(f"{status} {ref_dir.name} — rejeu")
        for p in problems:
            print(f"    - {p}")
        failed += bool(problems)
        if not is_llm:
            problems = rerun(ref_dir)
            if problems is None:
                print(f"  -   {ref_dir.name} — relance : pas relancé")
            else:
                print(f"{'OK   ' if not problems else 'ÉCHEC'} {ref_dir.name} — relance")
                for p in problems:
                    print(f"    - {p}")
                failed += bool(problems)
    print("\nTout est identique." if not failed else f"\n{failed} contrôle(s) en échec.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
