"""Aligneurs : une interface commune, une classe par méthode d'alignement.

Tout aligneur reçoit un verset hébreu et un verset grec (corpus.Verse) et
renvoie un VerseAlignment. Il sait lui-même sur quelle couche il travaille et
comment préparer le texte. Ajouter une méthode = écrire une sous-classe
d'Aligner et la déclarer dans make_aligner.
"""
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field

from normalize import norm_grc, norm_heb


@dataclass
class VerseAlignment:
    """Résultat de l'alignement d'un verset."""
    src: list                    # tokens hébreux montrés (un par token de la couche)
    tgt: list                    # tokens grecs montrés
    links: dict                  # méthode -> [(i, j), ...] (i : hébreu, j : grec)
    extra: dict = field(default_factory=dict)  # informations propres à l'aligneur (ex. llm_table)


class Aligner(ABC):
    """Interface commune à tous les aligneurs."""

    def __init__(self, layer: str = "w"):
        self.layer = layer       # couche dont les tokens sont reliés (w ou l)
        self.stats = Counter()   # compteurs affichés en fin d'expérience (vide si rien à dire)

    @abstractmethod
    def align(self, hv, gv) -> VerseAlignment:
        """Aligne le verset hébreu hv avec le verset grec gv."""


class SimAlignAligner(Aligner):
    """SimAlign (Jalili Sabet et al. 2020) sur un modèle à embeddings
    (mBERT, XLM-R, Glot500…). Reçoit les tokens normalisés (normalize.py)."""

    def __init__(self, model="bert", layer_nn=8, methods="mai", device="cpu",
                 layer="w", greek_accents=True):
        super().__init__(layer)
        self.greek_accents = greek_accents
        from simalign import SentenceAligner  # import tardif (lourd)
        self.model = SentenceAligner(model=model, token_type="bpe", matching_methods=methods,
                                     layer=layer_nn, device=device)

    def align(self, hv, gv) -> VerseAlignment:
        src = [norm_heb(t) for t in hv.tokens(self.layer)]
        tgt = [norm_grc(t, self.greek_accents) for t in gv.tokens(self.layer)]
        return VerseAlignment(src, tgt, self.model.get_word_aligns(src, tgt))


def make_aligner(cfg) -> Aligner:
    """Choisit et construit l'aligneur décrit par la configuration (config.Config)."""
    if cfg.aligner == "llm":
        from llm_align import OllamaAligner
        return OllamaAligner(cfg.llm_model, cfg.llm_url, think=cfg.llm_think, layer=cfg.tokens)
    return SimAlignAligner(cfg.model, cfg.layer, cfg.methods, cfg.device,
                           layer=cfg.tokens, greek_accents=cfg.greek_accents)
