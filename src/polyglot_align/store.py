"""Accès aux données de data/ : textes, gold, table des versets.

DataStore est le seul endroit du code qui connaît l'arborescence de data/ :

    data/he/<livre>.json          texte hébreu exporté (corpus.Corpus)
    data/lxx/<livre>.json         texte grec exporté
    data/gold_clean/<livre>.json  gold CATSS nettoyé, par livre grec (evaluation.Gold)
    data/verse_map.json           appariement des versets hébreu ↔ LXX (corpus.VerseMap)

Chaque fichier n'est lu qu'une fois : les objets sont gardés en mémoire (toute
la Bible, hébreu et grec : environ 90 Mo). Une expérience, ou un serveur,
garde un seul DataStore.
"""
from pathlib import Path
from typing import Iterator

from polyglot_align.corpus import Corpus, Verse, VerseMap
from polyglot_align.evaluation.gold import Gold


class DataStore:
    def __init__(self, root="data"):
        self.root = Path(root)
        self._corpora = {}       # (side, livre) -> Corpus
        self._golds = {}         # livre grec -> Gold
        self._verse_map = None

    def corpus(self, side: str, book: str) -> Corpus:
        """side = "he" ou "lxx" ; ex. store.corpus("lxx", "JudgA")."""
        if (side, book) not in self._corpora:
            self._corpora[side, book] = Corpus(self.root / side / f"{book}.json")
        return self._corpora[side, book]

    def gold(self, lxx_book: str) -> Gold:
        """Gold d'un livre grec : store.gold("Gen"), store.gold("JudgA")."""
        if lxx_book not in self._golds:
            self._golds[lxx_book] = Gold(self.root / "gold_clean" / f"{lxx_book}.json")
        return self._golds[lxx_book]

    @property
    def verse_map(self) -> VerseMap:
        if self._verse_map is None:
            self._verse_map = VerseMap(self.root / "verse_map.json")
        return self._verse_map

    def verse_pairs(self, he_book: str, lxx_book: str, only: str = None) -> list:
        """[(Verse hébreu, Verse grec)] d'un livre, appariés par la table, dans
        l'ordre du TM ; only (ex. "Gen.1", "Gen.1.1") : seulement ce chapitre
        ou ce verset, en numérotation hébraïque."""
        he, lxx = self.corpus("he", he_book), self.corpus("lxx", lxx_book)
        pairs = [(he[h], lxx[g]) for h, g in self.verse_map.pairs(he_book, lxx_book)]
        if only:
            pairs = [(hv, gv) for hv, gv in pairs if hv.ref == only or hv.ref.startswith(only + ".")]
        return pairs

    def table_pairs(self) -> Iterator[tuple[Verse, Verse]]:
        """Toutes les paires de versets de la table, livre par livre, dans
        l'ordre de la table (données d'apprentissage d'eflomal)."""
        for he_book, lxx_book in self.verse_map.book_pairs():
            yield from self.verse_pairs(he_book, lxx_book)
