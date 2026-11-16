"""Alignement d'un passage : parcourt les versets et écrit le JSONL (appelé par experiment.py).

Le travail sur chaque verset est fait par un Aligner (aligners/) ; ce module
ne fait que choisir les versets et écrire les résultats. Les versets sont
appariés par la table du gold (corpus.VerseMap) : un verset hébreu n'est aligné
qu'avec son équivalent LXX.

Sortie : JSONL, une ligne par verset (format dans alignment.py).
"""
from polyglot_align.alignment import AlignmentRecord
from polyglot_align.corpus import Corpus


def align(aligner, he_path, lxx_path, pairs, out_path, only=None) -> int:
    """Aligne les paires de versets `pairs` [(ch.vs TM, ch.vs LXX)] (ou seulement
    celles de `only`, ex. "Gen.1", en numérotation hébraïque) et écrit le JSONL.
    Renvoie le nombre de versets alignés."""
    he, lxx = Corpus(he_path), Corpus(lxx_path)
    if only:
        pairs = [(h, g) for h, g in pairs if he[h].ref == only or he[h].ref.startswith(only + ".")]
    with open(out_path, "w", encoding="utf-8") as out:
        for n, (he_key, lxx_key) in enumerate(pairs, 1):
            hv, gv = he[he_key], lxx[lxx_key]
            print(f"  {hv.ref} ({n}/{len(pairs)})", flush=True)
            res = aligner.align(hv, gv)
            out.write(AlignmentRecord.from_alignment(hv, gv, res).to_json() + "\n")
    return len(pairs)
