"""Aligneurs : une interface commune, une classe par méthode d'alignement.

Tout aligneur reçoit un verset hébreu et un verset grec (corpus.Verse) et
renvoie un VerseAlignment. Il sait lui-même sur quelle couche il travaille et
comment préparer le texte. Ajouter une méthode = écrire une sous-classe
d'Aligner (un module de ce sous-paquet) et la déclarer dans make_aligner
(aligners/__init__.py).
"""
from abc import ABC, abstractmethod
from collections import Counter

from polyglot_align.alignment import VerseAlignment


class Aligner(ABC):
    """Interface commune à tous les aligneurs."""

    def __init__(self, layer: str = "w"):
        self.layer = layer       # couche dont les tokens sont reliés (w, g ou l)
        self.stats = Counter()   # compteurs affichés en fin d'expérience (vide si rien à dire)

    def fit(self, verse_map, data_root) -> None:
        """Apprentissage sur le corpus (versets appariés par verse_map,
        corpus.VerseMap), appelé une fois avant l'alignement des passages.
        Ne fait rien par défaut (SimAlign, LLM) ; voir EflomalAligner."""

    @abstractmethod
    def align(self, hv, gv) -> VerseAlignment:
        """Aligne le verset hébreu hv avec le verset grec gv."""
