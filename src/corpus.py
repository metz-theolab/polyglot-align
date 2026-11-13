"""Textes exportés (data/he, data/lxx) : un livre = un Corpus de Verse.

Seul endroit du code qui lit le format d'export (couches t / w / l / g,
voir DECISIONS.md « Format d'export des textes »).
"""
import json
from dataclasses import dataclass
from pathlib import Path


def ref_key(ref: str) -> tuple:
    """Clé de tri d'une référence "Livre.ch.vs" (ou "ch.vs") dans l'ordre du texte."""
    parts = ref.split(".")
    return tuple(int(p) if p.isdigit() else p for p in parts)


@dataclass
class Verse:
    """Un verset et ses couches parallèles."""
    book: str
    chapter: str
    verse: str
    layers: dict                 # {"t": "...", "w": "a b c", "l": "...", "g": "0 0 1"}

    @property
    def key(self) -> str:
        """Référence sans le livre : "1.1"."""
        return f"{self.chapter}.{self.verse}"

    @property
    def ref(self) -> str:
        """Référence complète : "Gen.1.1"."""
        return f"{self.book}.{self.key}"

    def tokens(self, layer: str = "w") -> list:
        """Tokens d'une couche (w, l, g)."""
        return self.layers[layer].split(" ")

    def graphic_words(self, layer: str = "w") -> list:
        """Recolle les tokens d'un même mot graphique (couche g) :
        בְּ + רֵאשִׁית -> בְּרֵאשִׁית ; nom composé בית_אל -> בית אל."""
        words = {}
        for tok, k in zip(self.tokens(layer), self.tokens("g")):
            words[k] = words.get(k, "") + tok.replace("_", " ")
        return list(words.values())


class Corpus:
    """Un livre exporté : data/<he|lxx>/<livre>.json."""

    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        (self.book, chapters), = data.items()
        self.verses = {}          # "ch.vs" -> Verse, dans l'ordre du fichier
        for ch, verses in chapters.items():
            for vs, layers in verses.items():
                v = Verse(self.book, ch, vs, layers)
                self.verses[v.key] = v

    @classmethod
    def load(cls, side: str, book: str, root="data") -> "Corpus":
        """side = "he" ou "lxx" ; ex. Corpus.load("he", "Gen")."""
        return cls(Path(root) / side / f"{book}.json")

    def __getitem__(self, key: str) -> Verse:
        return self.verses[key]

    def __contains__(self, key: str) -> bool:
        return key in self.verses

    def keys(self):
        return self.verses.keys()
