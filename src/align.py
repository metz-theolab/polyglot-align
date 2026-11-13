"""Alignement d'un passage : parcourt les versets et écrit le JSONL (lancé par run.py).

Le travail sur chaque verset est fait par un Aligner (aligners.py) ; ce module
ne fait que choisir les versets et écrire les résultats.

Sortie : JSONL, une ligne par verset ; src et tgt sont les tokens montrés par
l'aligneur, dans l'ordre de l'export (indices reliables au gold par la couche g) :
  {"ref": "Gen.1.1", "src": [...], "tgt": [...], "links": {"inter": "0-0 1-1 ...", ...}}
"""
import json

from corpus import Corpus, ref_key


def align(aligner, he_path, lxx_path, out_path, only=None) -> int:
    """Aligne les versets communs aux deux exports (ou seulement `only`, ex.
    "Gen.1") et écrit le JSONL. Renvoie le nombre de versets alignés."""
    he, lxx = Corpus(he_path), Corpus(lxx_path)
    keys = sorted(he.keys() & lxx.keys(), key=ref_key)  # versets présents des deux côtés
    if only:
        keys = [k for k in keys if he[k].ref == only or he[k].ref.startswith(only + ".")]
    with open(out_path, "w", encoding="utf-8") as out:
        for n, key in enumerate(keys, 1):
            hv = he[key]
            print(f"  {hv.ref} ({n}/{len(keys)})", flush=True)
            res = aligner.align(hv, lxx[key])
            links = {m: " ".join(f"{a}-{b}" for a, b in sorted(p)) for m, p in res.links.items()}
            out.write(json.dumps({"ref": hv.ref, "src": res.src, "tgt": res.tgt, "links": links,
                                  **res.extra}, ensure_ascii=False) + "\n")
    return len(keys)
