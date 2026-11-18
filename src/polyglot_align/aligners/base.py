"""Aligneurs : une interface commune, une classe par méthode d'alignement.

Tout aligneur reçoit un verset hébreu et un verset grec (corpus.Verse) et
renvoie un VerseAlignment. Options communes, données par la config et comprises
par tous les aligneurs : `layer` (couche de tokens reliés : w, g, l), `hebrew`
(pointed, vocalized, unvocalized) et `greek` (accented, unaccented).

Ajouter une méthode = écrire une sous-classe d'Aligner (un module de ce
sous-paquet) qui déclare `name` (valeur de `type` dans la section `aligner:`
de la config), `PARAMS` (ses options et leurs valeurs par défaut) et, au
besoin, `check_params` ; puis l'ajouter au registre ALIGNERS
(aligners/__init__.py).
"""
from abc import ABC, abstractmethod
from collections import Counter
from typing import Iterable

from polyglot_align.alignment import VerseAlignment
from polyglot_align.corpus import Verse
from polyglot_align.normalize import HEB_PUNCT, norm_grc, norm_heb, norm_syr, strip_punct


class Aligner(ABC):
    """Interface commune à tous les aligneurs."""

    name = None                  # valeur de `type` dans la config (registre : aligners/__init__.py)
    PARAMS = {}                  # options propres à l'aligneur -> valeur par défaut

    def __init__(self, layer: str = "w", hebrew: str = "unvocalized", greek: str = "accented",
                 target: str = "lxx"):
        self.layer = layer       # couche dont les tokens sont reliés (w, g, l ou t)
        self.hebrew = hebrew     # pointed, vocalized, unvocalized (normalize.norm_heb)
        self.greek = greek       # accented, unaccented (normalize.norm_grc)
        self.target = target     # lxx (grec) ou syr (Peshitta : normalize.norm_syr)
        self.stats = Counter()   # compteurs affichés en fin d'expérience (vide si rien à dire)

    @classmethod
    def check_params(cls, params: dict) -> list:
        """Problèmes dans les options propres à l'aligneur (vérifiées par
        Config au démarrage, avant tout calcul) ; liste vide si tout va bien."""
        return []

    def normalized_tokens(self, hv, gv) -> tuple[list, list]:
        """Tokens de la couche `layer`, normalisés selon `hebrew` et `greek`
        (Peshitta : norm_syr ; couche t : ponctuation collée retirée)."""
        src = [norm_heb(t, self.hebrew) for t in hv.tokens(self.layer)]
        if self.layer == "t":
            src = [strip_punct(t, HEB_PUNCT) for t in src]
        if self.target == "syr":
            return src, [norm_syr(t) for t in gv.tokens(self.layer)]
        return src, [norm_grc(t, self.greek) for t in gv.tokens(self.layer)]

    def fit(self, pairs: Iterable[tuple[Verse, Verse]]) -> None:
        """Apprentissage sur des paires de versets (hébreu, grec), appelé une
        fois avant l'alignement des passages. L'aligneur ne choisit pas ses
        données : elles lui sont données (aujourd'hui toute la table des
        versets, DataStore.table_pairs). Ne fait rien par défaut (SimAlign,
        LLM : `pairs` n'est alors pas parcouru) ; voir EflomalAligner."""

    @abstractmethod
    def align(self, hv, gv) -> VerseAlignment:
        """Aligne le verset hébreu hv avec le verset grec gv."""
