"""Alignement d'un passage : parcourt les versets et écrit le JSONL (appelé par experiment.py).

Le travail sur chaque verset est fait par un Aligner (aligners/) ; ce module
ne fait que choisir les versets et écrire les résultats. Les versets sont
appariés par la table du gold (corpus.VerseMap) : un verset hébreu n'est aligné
qu'avec son équivalent LXX.

Sortie : JSONL, une ligne par verset ; src et tgt sont les tokens montrés par
l'aligneur, dans l'ordre de l'export (indices reliables au gold par la couche g) :
  {"ref": "Gen.1.1", "src": [...], "tgt": [...], "links": {"inter": "0-0 1-1 ...", ...}}
ref est la référence hébraïque ; si le verset LXX a un autre numéro, il est donné
dans ref_lxx (ex. "ref": "Ps.23.1", "ref_lxx": "Ps.22.1").
"""
import json

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
            links = {m: " ".join(f"{a}-{b}" for a, b in sorted(p)) for m, p in res.links.items()}
            ref_lxx = {"ref_lxx": gv.ref} if lxx_key != he_key else {}
            out.write(json.dumps({"ref": hv.ref, **ref_lxx, "src": res.src, "tgt": res.tgt,
                                  "links": links, **res.extra}, ensure_ascii=False) + "\n")
    return len(pairs)
