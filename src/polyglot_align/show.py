"""Affiche l'alignement d'un verset, pour le relire à la main.

Usage (depuis la racine du projet) :
    polyglot-align show results/<expérience>/Gen.1.jsonl Gen.1.1
    polyglot-align show results/<expérience>/Gen.1.jsonl Gen.1.1 itermax
"""
from polyglot_align.alignment import read_jsonl


def show(jsonl_path, ref, method="inter"):
    """Pour chaque mot hébreu, ses correspondants grecs (∅ = non aligné)."""
    for rec in read_jsonl(jsonl_path):
        if rec.ref != ref:
            continue
        pairs = rec.links[method]
        for i, w in enumerate(rec.src):
            tgt = [rec.tgt[b] for a, b in pairs if a == i]
            print(f"{w:>12}  ↔  {' '.join(tgt) or '∅'}")
        aligned = {b for _, b in pairs}
        orphans = [w for j, w in enumerate(rec.tgt) if j not in aligned]
        print(f"{'grec non aligné':>12}  :  {' '.join(orphans) or '—'}")
        return
    print(f"{ref} absent de {jsonl_path}")
