"""Alignement mot à mot hébreu – grec avec SimAlign (bibliothèque, lancée par run.py).

Entrée  : deux exports {"Gen": {"1": {"1": {"t": …, "w": "tok tok …", …}}}}
Sortie  : JSONL, une ligne par verset ; src et tgt sont les tokens de la couche
          alignée, dans l'ordre de l'export (indices reliables au gold par g) :
  {"ref": "Gen.1.1", "src": [...], "tgt": [...], "links": {"inter": "0-0 1-1 ...", ...}}
"""
import json
from pathlib import Path

from normalize import norm_grc, norm_heb


def load(path: Path, tokens: str = "w") -> dict[str, list[str]]:
    """{"Gen": {"1": {"1": {"w": "a b c"}}}} -> {"Gen.1.1": ["a", "b", "c"]}
    tokens : couche alignée, "w" (formes) ou "l" (lemmes)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {f"{b}.{c}.{v}": d[tokens].split(" ")
            for b, chs in data.items() for c, vs in chs.items() for v, d in vs.items()}


def ref_key(ref: str):
    b, c, v = ref.split(".")
    return (b, int(c) if c.isdigit() else c, int(v) if v.isdigit() else v)


def make_aligner(model="bert", layer=8, methods="mai", device="cpu"):
    """Charge SimAlign une seule fois (lourd)."""
    from simalign import SentenceAligner
    return SentenceAligner(model=model, token_type="bpe", matching_methods=methods,
                           layer=layer, device=device)


def align(aligner, he_path, lxx_path, out_path, tokens="w", only=None, accents=True) -> int:
    """Aligne les versets communs aux deux exports (ou seulement `only`, ex.
    "Gen.1") et écrit le JSONL. Renvoie le nombre de versets alignés.
    SimAlign reçoit les tokens normalisés (normalize.py) ; un aligneur qui
    travaille sur le texte (uses_text, ex. le LLM) reçoit les formes d'origine
    (pointées, accentuées) et la couche g (mots graphiques)."""
    src, tgt = load(he_path, tokens), load(lxx_path, tokens)
    common = sorted(src.keys() & tgt.keys(), key=ref_key)
    if only:
        common = [r for r in common if r == only or r.startswith(only + ".")]
    uses_text = getattr(aligner, "uses_text", False)
    if uses_text:
        src_g, tgt_g = load(he_path, "g"), load(lxx_path, "g")
    with open(out_path, "w", encoding="utf-8") as out:
        for k, ref in enumerate(common, 1):
            print(f"  {ref} ({k}/{len(common)})", flush=True)
            extra = {}
            if uses_text:
                s_tok, t_tok = src[ref], tgt[ref]
                res, extra = aligner.align_verse(s_tok, src_g[ref], t_tok, tgt_g[ref])
            else:
                s_tok = [norm_heb(t) for t in src[ref]]
                t_tok = [norm_grc(t, accents) for t in tgt[ref]]
                res = aligner.get_word_aligns(s_tok, t_tok)
            links = {m: " ".join(f"{a}-{b}" for a, b in sorted(p)) for m, p in res.items()}
            out.write(json.dumps({"ref": ref, "src": s_tok, "tgt": t_tok, "links": links, **extra},
                                 ensure_ascii=False) + "\n")
    return len(common)
