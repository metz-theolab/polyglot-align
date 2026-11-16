"""AlignerService : le TextAligner de polyglot_align, chargé une fois, partagé.

- chargement en arrière-plan (environ 10 s : données, table de segmentation,
  dictabert-seg) : l'API répond tout de suite, /health dit « loading » puis
  « ready » (contrôle de santé du futur conteneur Docker) ;
- un alignement à la fois (verrou) : eflomal occupe tous les cœurs pendant
  son apprentissage ; deux apprentissages simultanés se ralentiraient.
"""
import logging
import threading
import time
from typing import Callable

from polyglot_align.segment import consonantal_words, hebrew_verse

log = logging.getLogger(__name__)


class NotReady(Exception):
    """Modèles pas encore chargés (ou chargement en erreur)."""


class AlignerService:
    def __init__(self, factory: Callable):
        """factory() -> polyglot_align.textalign.TextAligner (ou équivalent, en test)."""
        self._factory = factory
        self._lock = threading.Lock()
        self.aligner = None
        self.status, self.detail, self.loading_s = "loading", None, None

    def load(self) -> None:
        """Charge le TextAligner ; à lancer une fois (en arrière-plan au démarrage)."""
        t0 = time.perf_counter()
        try:
            self.aligner = self._factory()
        except Exception as e:                   # l'API reste joignable et dit pourquoi
            self.status, self.detail = "error", f"{type(e).__name__}: {e}"
            log.exception("chargement des modèles impossible")
            return
        self.loading_s = round(time.perf_counter() - t0, 1)
        self.status = "ready"
        log.info("modèles chargés en %.1f s", self.loading_s)

    def _ready(self):
        if self.status != "ready":
            raise NotReady(self.detail or "modèles en cours de chargement")
        return self.aligner

    def unknown_words(self, hebrew_text: str) -> list:
        """Mots graphiques absents de la table de segmentation (BHSA) : découpés
        par dictabert-seg."""
        # CombinedSegmenter.table est un TableSegmenter ; TableSegmenter.table, le dictionnaire
        table = getattr(self._ready().segmenter, "table", None)
        table = getattr(table, "table", table)
        if not isinstance(table, dict):
            return []
        return [w for w in consonantal_words(hebrew_text) if w not in table]

    def align_many(self, pairs: list) -> tuple[list, float]:
        """[(hébreu, grec)] -> ([TextAlignment], durée en s). Lève ValueError si
        un texte est vide (aucun mot hébreu, aucun mot grec)."""
        aligner = self._ready()
        with self._lock:
            t0 = time.perf_counter()
            results = aligner.align_many(pairs)
            return results, round(time.perf_counter() - t0, 2)

    def segment(self, hebrew_text: str):
        """Texte hébreu -> Verse (couches t, w, g), sans alignement."""
        return hebrew_verse(hebrew_text, self._ready().segmenter)
