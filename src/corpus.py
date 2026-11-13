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
        """Tokens d'une couche :
        w : un token par mot BHSA, proclitiques séparés (בְּ רֵאשִׁית) ;
        l : lexème de chaque token de w ;
        g : un token par mot graphique (בְּרֵאשִׁית), tokens de w recollés
            (nom composé gardé en un token : בית_אל)."""
        if layer == "g":
            return self._join_graphic("w", keep_compound=True)
        return self.layers[layer].split(" ")

    def graphic_numbers(self) -> list:
        """Numéro du mot graphique de chaque token de w (couche g de l'export)."""
        return self.layers["g"].split(" ")

    def graphic_words(self, layer: str = "w") -> list:
        """Mots graphiques pour l'affichage (prompt du LLM) : tokens recollés,
        nom composé בית_אל -> « בית אל ». layer = w ou l (g = w)."""
        return self._join_graphic("w" if layer == "g" else layer, keep_compound=False)

    def _join_graphic(self, layer: str, keep_compound: bool) -> list:
        """Recolle les tokens de `layer` qui ont le même numéro de mot graphique."""
        words = {}
        for tok, k in zip(self.tokens(layer), self.graphic_numbers()):
            words[k] = words.get(k, "") + (tok if keep_compound else tok.replace("_", " "))
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
