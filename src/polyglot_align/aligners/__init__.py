"""Aligneurs : interface commune (base.py), une classe par méthode.

    simalign.py   SimAlignAligner (mBERT, XLM-R, Glot500…)
    eflomal.py    EflomalAligner (statistique, apprend sur toute la table des versets)
    llm.py        OllamaAligner (LLM local)

ALIGNERS est le registre : valeur de `type` dans la section `aligner:` de la
config -> classe. Les bibliothèques lourdes (simalign, eflomal) ne sont
importées qu'à la construction ou à l'apprentissage de l'aligneur choisi.
"""
from polyglot_align.aligners.base import Aligner, VerseAlignment
from polyglot_align.aligners.eflomal import EflomalAligner
from polyglot_align.aligners.llm import OllamaAligner
from polyglot_align.aligners.simalign import SimAlignAligner

__all__ = ["Aligner", "VerseAlignment", "ALIGNERS", "make_aligner"]

ALIGNERS = {cls.name: cls for cls in (SimAlignAligner, EflomalAligner, OllamaAligner)}


def make_aligner(cfg) -> Aligner:
    """Construit l'aligneur décrit par la configuration (config.Config) :
    options propres (section `aligner:`) et options communes (tokens, hebrew, greek)."""
    cls = ALIGNERS[cfg.aligner_type]
    # target seulement pour la Peshitta (Config n'y autorise qu'eflomal)
    target = {"target": cfg.target} if cfg.target != "lxx" else {}
    return cls(**cfg.aligner_params, layer=cfg.tokens, hebrew=cfg.hebrew, greek=cfg.greek, **target)
