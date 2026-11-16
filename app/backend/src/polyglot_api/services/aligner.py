"""AlignerService : les aligneurs de textes de polyglot_align, chargés une fois.

- chargement en arrière-plan : le socle commun (données, segmenteur de
  l'hébreu) puis chaque algorithme, dans l'ordre ; le premier (eflomal) est
  l'algorithme par défaut : l'API est « ready » dès qu'il l'est ;
- un état par algorithme : loading, ready, unavailable (avec la raison :
  Ollama absent, modèle manquant…) ; un algorithme indisponible ne bloque pas
  les autres ; ceux qui ont une vérification (LLM : Ollama joignable ?) sont
  revérifiés à la demande ;
- un alignement à la fois, tous algorithmes confondus (verrou) : eflomal et
  les modèles occupent tous les cœurs.
"""
import logging
import threading
import time
from typing import Callable

from polyglot_align.segment import consonantal_words, hebrew_verse

log = logging.getLogger(__name__)


class NotReady(Exception):
    """Algorithme pas encore chargé, ou indisponible."""


class UnknownAlgorithm(Exception):
    """Algorithme que l'API ne propose pas."""


class AlignerService:
    def __init__(self, base: Callable, factories: dict, checks: dict | None = None):
        """base() -> {"segmenter": …, …} : socle commun, chargé une fois ;
        factories : {nom: f(socle) -> aligneur de textes}, dans l'ordre (le
        premier est l'algorithme par défaut) ;
        checks : {nom: f() -> raison d'indisponibilité, ou None}."""
        self._base_factory, self._factories, self._checks = base, dict(factories), dict(checks or {})
        self._lock = threading.Lock()
        self.base = None
        self.algorithms = {name: {"status": "loading", "detail": None, "aligner": None}
                           for name in self._factories}
        self.status, self.detail, self.loading_s = "loading", None, None

    @property
    def default(self) -> str:
        return next(iter(self._factories))

    def load(self) -> None:
        """Charge le socle puis chaque algorithme ; à lancer une fois (en
        arrière-plan au démarrage)."""
        t0 = time.perf_counter()
        try:
            self.base = self._base_factory()
        except Exception as e:                   # l'API reste joignable et dit pourquoi
            self.status, self.detail = "error", f"{type(e).__name__}: {e}"
            for a in self.algorithms.values():
                a.update(status="unavailable", detail=self.detail)
            log.exception("chargement impossible")
            return
        for name in self._factories:
            self._load_one(name)
            if name == self.default:
                a = self.algorithms[name]
                self.status = "ready" if a["status"] == "ready" else "error"
                self.detail = a["detail"]
                self.loading_s = round(time.perf_counter() - t0, 1)
                log.info("%s prêt en %.1f s", name, self.loading_s)

    def _load_one(self, name: str) -> None:
        a = self.algorithms[name]
        reason = self._checks[name]() if name in self._checks else None
        if reason:
            a.update(status="unavailable", detail=reason, aligner=None)
            log.info("%s indisponible : %s", name, reason)
            return
        try:
            a.update(aligner=self._factories[name](self.base), status="ready", detail=None)
            log.info("%s prêt", name)
        except Exception as e:
            a.update(status="unavailable", detail=f"{type(e).__name__}: {e}", aligner=None)
            log.exception("%s : chargement impossible", name)

    def refresh(self) -> None:
        """Revérifie les algorithmes indisponibles qui ont une vérification
        (ex. Ollama démarré après l'API)."""
        if self.base is None:
            return
        for name, a in self.algorithms.items():
            if a["status"] == "unavailable" and name in self._checks:
                self._load_one(name)

    def _aligner(self, name: str):
        if name not in self.algorithms:
            raise UnknownAlgorithm(f"unknown algorithm: {name} (available: {', '.join(self.algorithms)})")
        a = self.algorithms[name]
        if a["status"] == "loading":
            raise NotReady(f"{name}: model still loading, retry in a few seconds")
        if a["status"] != "ready":
            raise NotReady(f"{name} unavailable: {a['detail']}")
        return a["aligner"]

    def _segmenter(self):
        if self.base is None:
            raise NotReady(self.detail or "models are still loading, retry in a few seconds")
        return self.base["segmenter"]

    def unknown_words(self, hebrew_text: str) -> list:
        """Mots graphiques absents de la table de segmentation (BHSA) : découpés
        par dictabert-seg."""
        # CombinedSegmenter.table est un TableSegmenter ; TableSegmenter.table, le dictionnaire
        table = getattr(self._segmenter(), "table", None)
        table = getattr(table, "table", table)
        if not isinstance(table, dict):
            return []
        return [w for w in consonantal_words(hebrew_text) if w not in table]

    def align_many(self, pairs: list, algorithm: str | None = None) -> tuple[list, float, object]:
        """[(hébreu, grec)] -> ([TextAlignment], durée en s, aligneur). Lève
        UnknownAlgorithm, NotReady, ou ValueError si un texte est vide."""
        aligner = self._aligner(algorithm or self.default)
        with self._lock:
            t0 = time.perf_counter()
            results = aligner.align_many(pairs)
            return results, round(time.perf_counter() - t0, 2), aligner

    def segment(self, hebrew_text: str):
        """Texte hébreu -> Verse (couches t, w, g), sans alignement."""
        return hebrew_verse(hebrew_text, self._segmenter())
