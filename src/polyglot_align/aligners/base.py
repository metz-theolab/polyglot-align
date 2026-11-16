"""Aligneurs : une interface commune, une classe par méthode d'alignement.

Tout aligneur reçoit un verset hébreu et un verset grec (corpus.Verse) et
renvoie un VerseAlignment. Il sait lui-même sur quelle couche il travaille et
comment préparer le texte. Ajouter une méthode = écrire une sous-classe
d'Aligner (un module de ce sous-paquet) et la déclarer dans make_aligner
(aligners/__init__.py).
"""
from abc import ABC, abstractmethod
from collections import Counter
from typing import Iterable

from polyglot_align.alignment import VerseAlignment
from polyglot_align.corpus import Verse


class Aligner(ABC):
    """Interface commune à tous les aligneurs."""

    def __init__(self, layer: str = "w"):
        self.layer = layer       # couche dont les tokens sont reliés (w, g ou l)
        self.stats = Counter()   # compteurs affichés en fin d'expérience (vide si rien à dire)

    def fit(self, pairs: Iterable[tuple[Verse, Verse]]) -> None:
        """Apprentissage sur des paires de versets (hébreu, grec), appelé une
        fois avant l'alignement des passages. L'aligneur ne choisit pas ses
        données : elles lui sont données (aujourd'hui toute la table des
        versets, DataStore.table_pairs). Ne fait rien par défaut (SimAlign,
        LLM : `pairs` n'est alors pas parcouru) ; voir EflomalAligner."""

    @abstractmethod
    def align(self, hv, gv) -> VerseAlignment:
        """Aligne le verset hébreu hv avec le verset grec gv."""
