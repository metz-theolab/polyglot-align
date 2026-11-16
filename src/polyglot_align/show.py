"""Affiche l'alignement d'un verset, pour le relire à la main.

Usage (depuis la racine du projet) :
    polyglot-align show results/<expérience>/Gen.1.jsonl Gen.1.1
    polyglot-align show results/<expérience>/Gen.1.jsonl Gen.1.1 itermax
"""
import json


def show(jsonl_path, ref, method="inter"):
    """Pour chaque mot hébreu, ses correspondants grecs (∅ = non aligné)."""
    for line in open(jsonl_path, encoding="utf-8"):
        d = json.loads(line)
        if d["ref"] != ref:
            continue
        pairs = [tuple(map(int, l.split("-"))) for l in d["links"][method].split()]
        for i, w in enumerate(d["src"]):
            tgt = [d["tgt"][b] for a, b in pairs if a == i]
            print(f"{w:>12}  ↔  {' '.join(tgt) or '∅'}")
        aligned = {b for _, b in pairs}
        orphans = [w for j, w in enumerate(d["tgt"]) if j not in aligned]
        print(f"{'grec non aligné':>12}  :  {' '.join(orphans) or '—'}")
        return
    print(f"{ref} absent de {jsonl_path}")

