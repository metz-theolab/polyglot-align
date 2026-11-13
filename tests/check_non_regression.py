"""Test de non-régression de la restructuration (voir DECISIONS.md).

Deux contrôles, contre les références produites avant la restructuration
(tests/reference/<nom>/ : config, alignements JSONL, scores) :

1. Rejeu (toutes les expériences, sans relancer les modèles) : on réévalue
   les alignements de référence avec le code actuel, et pour le LLM on
   reconvertit d'abord ses tableaux (champ llm_table) en liens. Les liens et
   les scores doivent être identiques. Teste tout notre code (conversion,
   projection sur le gold, mesures), rapidement.

2. Relance (SimAlign seulement) : si results/<nom>/ existe, ses fichiers
   doivent être identiques à la référence, octet par octet. Le LLM n'est pas
   comparé ainsi : il n'est pas déterministe, même à température 0 avec une
   graine fixe (constaté le 2026-11-13 sur Gn 3:6).

Usage (depuis la racine du projet) :
    python tests/check_non_regression.py
    (après restructuration, relancer d'abord les expériences SimAlign :
     python src/run.py experiments/<nom>.yaml)
"""
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from evaluate import evaluate_book          # noqa: E402
from llm_align import table_to_links        # noqa: E402

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
        lines = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines()]
        if not lines:
            problems.append(f"{label} : JSONL de référence vide (référence invalide)")
            continue

        # conversion tableau -> liens (LLM)
        for d in lines:
            if "llm_table" in d:
                links = table_to_links(d["src"], d["tgt"], d["llm_table"])
                if " ".join(f"{a}-{b}" for a, b in links) != d["links"]["llm"]:
                    problems.append(f"{label} {d['ref']} : la conversion du tableau donne d'autres liens")

        # réévaluation
        with tempfile.TemporaryDirectory() as tmp:
            res = evaluate_book(jsonl, ROOT / f"data/he/{he_book}.json", ROOT / f"data/lxx/{lxx_book}.json",
                                ROOT / f"data/gold_clean/{lxx_book}.json")
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
