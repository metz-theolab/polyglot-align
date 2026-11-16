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
    """Un livre exporté : data/<he|lxx>/<livre>.json (lu par store.DataStore)."""

    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        (self.book, chapters), = data.items()
        self.verses = {}          # "ch.vs" -> Verse, dans l'ordre du fichier
        for ch, verses in chapters.items():
            for vs, layers in verses.items():
                v = Verse(self.book, ch, vs, layers)
                self.verses[v.key] = v

    def __getitem__(self, key: str) -> Verse:
        return self.verses[key]

    def __contains__(self, key: str) -> bool:
        return key in self.verses

    def keys(self):
        return self.verses.keys()


class VerseMap:
    """Table d'équivalence des versets hébreu ↔ LXX (data/verse_map.json,
    produite par data/make_verse_map.py à partir du gold). Seule source de
    l'appariement des versets : un verset hébreu n'est aligné qu'avec son
    équivalent LXX de la table (groupes 1 ↔ 1, voir DECISIONS.md)."""

    def __init__(self, path):
        self.books = json.loads(Path(path).read_text(encoding="utf-8"))

    def pairs(self, he_book: str, lxx_book: str) -> list:
        """[(ch.vs TM, ch.vs LXX)] du livre, dans l'ordre du TM."""
        if lxx_book not in self.books:
            raise KeyError(f"{lxx_book} absent de la table des versets (data/verse_map.json)")
        entry = self.books[lxx_book]
        if entry["he"] != he_book:
            raise KeyError(f"{lxx_book} est apparié à {entry['he']} dans la table, pas à {he_book}")
        return [tuple(p) for p in entry["pairs"]]

    def book_pairs(self) -> list:
        """[(livre hébreu, livre grec)] de toute la table."""
        return [(e["he"], lxx_book) for lxx_book, e in self.books.items()]
