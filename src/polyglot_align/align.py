"""Alignement d'un passage : parcourt les versets et écrit le JSONL (appelé par experiment.py).

Le travail sur chaque verset est fait par un Aligner (aligners/) ; ce module
ne fait qu'écrire les résultats. Les paires de versets viennent de la table
d'appariement (DataStore.verse_pairs) : un verset hébreu n'est aligné qu'avec
son équivalent LXX.

Sortie : JSONL, une ligne par verset (format dans alignment.py).
"""
from polyglot_align.alignment import AlignmentRecord


def align(aligner, pairs, out_path) -> int:
    """Aligne les paires de versets `pairs` [(Verse hébreu, Verse grec)] et
    écrit le JSONL. Renvoie le nombre de versets alignés."""
    with open(out_path, "w", encoding="utf-8") as out:
        for n, (hv, gv) in enumerate(pairs, 1):
            print(f"  {hv.ref} ({n}/{len(pairs)})", flush=True)
            res = aligner.align(hv, gv)
            out.write(AlignmentRecord.from_alignment(hv, gv, res).to_json() + "\n")
    return len(pairs)
