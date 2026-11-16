"""Aligneurs : interface commune (base.py), une classe par méthode.

    simalign.py   SimAlignAligner (mBERT, XLM-R, Glot500…)
    eflomal.py    EflomalAligner (statistique, apprend sur toute la table des versets)
    llm.py        OllamaAligner (LLM local)

Les modules lourds (simalign, eflomal) ne sont importés qu'à la construction
de l'aligneur choisi.
"""
from polyglot_align.aligners.base import Aligner, VerseAlignment

__all__ = ["Aligner", "VerseAlignment", "make_aligner"]


def make_aligner(cfg) -> Aligner:
    """Choisit et construit l'aligneur décrit par la configuration (config.Config)."""
    if cfg.aligner == "llm":
        from polyglot_align.aligners.llm import OllamaAligner
        return OllamaAligner(cfg.llm_model, cfg.llm_url, think=cfg.llm_think, layer=cfg.tokens,
                             hebrew=cfg.llm_hebrew)
    if cfg.aligner == "eflomal":
        from polyglot_align.aligners.eflomal import EflomalAligner
        return EflomalAligner(layer=cfg.tokens, greek_accents=cfg.greek_accents,
                              hebrew_vocalization=cfg.hebrew_vocalization)
    from polyglot_align.aligners.simalign import SimAlignAligner
    return SimAlignAligner(cfg.model, cfg.layer, cfg.methods, cfg.device, layer=cfg.tokens,
                           greek_accents=cfg.greek_accents,
                           hebrew_vocalization=cfg.hebrew_vocalization)
