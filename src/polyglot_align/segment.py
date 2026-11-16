"""Segmentation de l'hébreu en mots BHSA (proclitiques séparés), pour l'app de test.

Voir DECISIONS.md « Segmentation de l'hébreu saisi, pour l'app de test ».
Un texte saisi (vocalisé ou non) arrive en mots graphiques (בְּרֵאשִׁית) ; le
corpus est découpé comme BHSA (ב ראשית). Le découpage se fait sur le texte
consonantique et produit des tokens consonantiques ; l'article absorbé par la
préposition est ignoré, comme dans BHSA (בַּבַּיִת et בְּבֵית -> ב בית).

    consonantal_words(text)   texte -> mots graphiques consonantiques
    Segmenter                 interface : segment(text) -> tokens
    TableSegmenter            découpage le plus fréquent de chaque forme dans
                              BHSA, préfixe détaché pour une forme inconnue
    DictaSegmenter            dictabert-seg (Dicta), préfixes coupés lettre
                              par lettre (convention BHSA)
    CombinedSegmenter         table pour les formes connues, dictabert-seg pour
                              les autres (méthode retenue pour l'app)
    hebrew_verse, greek_verse texte saisi -> corpus.Verse (couches t, w, g),
                              comme un verset du corpus, à donner aux aligneurs
"""
import re
import unicodedata
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from typing import Iterable

from polyglot_align.corpus import Verse
from polyglot_align.normalize import norm_heb

PREFIXES = "והבכלמש"          # proclitiques séparés par BHSA
MAQAF = "־"               # ־ : relie deux mots graphiques


def consonantal(text: str) -> str:
    """Lettres hébraïques seules (sans voyelles, accents, ponctuation)."""
    return re.sub(r"[^א-ת]", "", norm_heb(text, "unvocalized"))


# signes gardés dans un mot pointé : lettres, voyelles, accents, dagesh, points,
# lettres précomposées (שׁ U+FB2A, שׂ U+FB2B : 253 dans 232 versets du corpus) ;
# retirés : maqqef (séparateur), paseq, sof pasuq, nun inversé, ponctuation
POINTED_KEEP = re.compile(r"[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7\u05d0-\u05ea"
                          r"\ufb1d-\ufb4e]")


def consonantal_words(text: str) -> list:
    """Texte (vocalisé ou non) -> mots graphiques consonantiques ; le maqqef
    sépare deux mots graphiques, comme dans la couche g du corpus
    (אֶת־הָרָקִיעַ -> את, הרקיע)."""
    words = (consonantal(w) for w in re.split(rf"[\s{MAQAF}]+", text))
    return [w for w in words if w]


def pointed_words(text: str) -> list:
    """Texte -> mots graphiques tels qu'écrits (voyelles et accents gardés,
    ponctuation retirée), séparés comme consonantal_words."""
    words = ("".join(POINTED_KEEP.findall(w)) for w in re.split(rf"[\s{MAQAF}]+", text))
    return [w for w in words if consonantal(w)]


def split_pointed(word: str, parts: list) -> list:
    """Reporte un découpage consonantique sur le mot écrit : coupe aux mêmes
    lettres, chaque signe restant attaché à la lettre qui le précède
    (בַּבַּיִת, [ב, בית] -> בַּ, בַּיִת)."""
    starts, pos = set(), 0
    for p in parts[:-1]:
        pos += len(p)
        starts.add(pos)
    pieces, letters = [""], 0
    for ch in word:
        if consonantal(ch):            # lettre, simple ou précomposée (שׁ)
            if letters in starts:
                pieces.append("")
            letters += 1
        pieces[-1] += ch
    return pieces


def bhsa_words(verse) -> list:
    """Mots graphiques d'un verset du corpus et leur découpage BHSA :
    [(forme consonantique, découpage, ou None si non utilisable)]. Noms
    composés (בית_אל : un token w pour deux mots graphiques) : None."""
    groups = {}
    for tok, k in zip(verse.tokens("w"), verse.graphic_numbers()):
        groups.setdefault(k, []).append(tok)
    words = []
    for toks in groups.values():
        parts = tuple(consonantal(t) for t in toks)
        ok = all(parts) and not any("_" in t for t in toks)
        words.append(("".join(parts), parts if ok else None))
    return words


class Segmenter(ABC):
    """Interface commune : mots graphiques consonantiques -> leur découpage."""

    name = None

    @abstractmethod
    def segment_words(self, words: list) -> list:
        """Mots graphiques consonantiques d'une même phrase -> pour chacun, la
        liste de ses tokens (dont la concaténation redonne le mot)."""

    def segment(self, text: str) -> list:
        """Texte hébreu (vocalisé ou non) -> tokens consonantiques à la BHSA."""
        return [t for parts in self.segment_words(consonantal_words(text)) for t in parts]


class TableSegmenter(Segmenter):
    """Découpage le plus fréquent de chaque forme consonantique, appris sur
    des exemples (mot graphique, découpage BHSA). Forme inconnue : un
    préfixe (ו ה ב כ ל מ ש) est détaché si le reste est une forme connue (ou
    se découpe ainsi, jusqu'à 3 préfixes) ; sinon le mot reste entier."""

    name = "table"

    def __init__(self):
        self.table = {}          # forme -> découpage (tuple de tokens)

    def fit(self, examples: Iterable[tuple]) -> "TableSegmenter":
        """examples : (forme consonantique, découpage BHSA)."""
        counts = defaultdict(Counter)
        for word, parts in examples:
            counts[word][tuple(parts)] += 1
        self.table = {w: c.most_common(1)[0][0] for w, c in counts.items()}
        return self

    def segment_word(self, word: str) -> list:
        if word in self.table:
            return list(self.table[word])
        return self._detach(word, depth=0) or [word]

    def _detach(self, word: str, depth: int):
        """Préfixe + reste connu ; None si rien ne convient."""
        if depth >= 3 or len(word) < 2 or word[0] not in PREFIXES:
            return None
        rest = word[1:]
        if rest in self.table:
            return [word[0]] + list(self.table[rest])
        tail = self._detach(rest, depth + 1)
        return [word[0]] + tail if tail else None

    def segment_words(self, words: list) -> list:
        return [self.segment_word(w) for w in words]

    @classmethod
    def from_store(cls, store, books=None, keep_chapter=None) -> "TableSegmenter":
        """Table construite sur le corpus hébreu (store.DataStore) : tous les
        livres et chapitres par défaut ; books, keep_chapter(chapitre) -> bool
        pour n'en garder qu'une partie (évaluation)."""
        examples = []
        for b in books or store.books("he"):
            for v in store.corpus("he", b).verses.values():
                if keep_chapter is None or keep_chapter(v.chapter):
                    examples += [(w, p) for w, p in bhsa_words(v) if p]
        return cls().fit(examples)


def split_dicta_word(item: list, word: str) -> list:
    """Sortie de dictabert-seg pour un mot ([préfixes…, reste], ex. ["וב",
    "שמים"]) -> tokens à la BHSA : préfixes coupés lettre par lettre (ו ב
    שמים). Si la sortie ne redonne pas le mot, le mot reste entier."""
    *prefixes, rest = item
    parts = [c for p in prefixes for c in p] + [rest]
    return parts if "".join(parts) == word else [word]


class DictaSegmenter(Segmenter):
    """dictabert-seg (dicta-il/dictabert-seg) : segmenteur de préfixes de
    l'hébreu moderne, sur texte consonantique, avec le contexte de la phrase."""

    name = "dictabert-seg"

    def __init__(self, model: str = "dicta-il/dictabert-seg", device: str = "cpu",
                 batch_size: int = 32):
        from huggingface_hub import hf_hub_download     # imports tardifs (lourds)
        from safetensors.torch import load_file
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging as hf_logging
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        # le rapport de chargement de transformers annonce la tête « MISSING » :
        # trompeur, elle est rechargée juste après (toutes les clés vérifiées)
        verbosity = hf_logging.get_verbosity()
        hf_logging.set_verbosity_error()
        try:
            self.model = AutoModel.from_pretrained(model, trust_remote_code=True)
        finally:
            hf_logging.set_verbosity(verbosity)
        # transformers 5 ne retrouve plus la tête de segmentation, enregistrée
        # à la racine du fichier de poids (classifiers.*, transform.*…) alors
        # que le modèle l'attend sous prefix.* : rechargée explicitement
        state = load_file(hf_hub_download(model, "model.safetensors"))
        head = {k: v for k, v in state.items() if not k.startswith("bert.")}
        self.model.prefix.load_state_dict(head, strict=True)
        self.model.to(device).eval()
        self.batch_size = batch_size

    def segment_sentences(self, sentences: list) -> list:
        """Phrases (listes de mots graphiques consonantiques) -> découpage de
        chaque mot, par lots."""
        import torch
        out = []
        for i in range(0, len(sentences), self.batch_size):
            batch = sentences[i:i + self.batch_size]
            with torch.no_grad():
                preds = self.model.predict([" ".join(s) for s in batch], self.tokenizer)
            for words, pred in zip(batch, preds):
                items = [p for p in pred if p not in (["[CLS]"], ["[SEP]"])]
                if len(items) != len(words):          # découpage du modèle inattendu
                    out.append([[w] for w in words])
                else:
                    out.append([split_dicta_word(it, w) for it, w in zip(items, words)])
        return out

    def segment_words(self, words: list) -> list:
        return self.segment_sentences([words])[0]


class CombinedSegmenter(Segmenter):
    """Table pour les formes connues de BHSA, dictabert-seg pour les autres
    (DECISIONS.md : 98,68 % de mots découpés comme BHSA à l'évaluation, contre
    96,05 % pour la table seule et 95,68 % pour dictabert-seg seul).
    dictabert-seg voit toute la phrase (contexte) mais n'est appelé que si la
    phrase contient au moins une forme inconnue."""

    name = "table+dictabert-seg"

    def __init__(self, table: TableSegmenter, dicta: DictaSegmenter):
        self.table, self.dicta = table, dicta

    @classmethod
    def from_store(cls, store, device: str = "cpu") -> "CombinedSegmenter":
        """Table sur tout le corpus hébreu, dictabert-seg chargé."""
        return cls(TableSegmenter.from_store(store), DictaSegmenter(device=device))

    def segment_sentences(self, sentences: list) -> list:
        known = self.table.table
        need = [i for i, s in enumerate(sentences) if any(w not in known for w in s)]
        dicta = (dict(zip(need, self.dicta.segment_sentences([sentences[i] for i in need])))
                 if need else {})
        return [[self.table.segment_word(w) if w in known else dicta[i][k] for k, w in enumerate(s)]
                for i, s in enumerate(sentences)]

    def segment_words(self, words: list) -> list:
        return self.segment_sentences([words])[0]


# --- texte saisi -> verset, comme dans le corpus -------------------------------


def _ref(ref: str):
    book, chapter, verse = ref.split(".")
    return book, chapter, verse


def hebrew_verse(text: str, segmenter: Segmenter, ref: str = "A.1.1") -> Verse:
    """Texte hébreu saisi (vocalisé ou non) -> Verse aux couches t (texte),
    w (mots BHSA, tels qu'écrits : בַּ בַּיִת) et g (numéro du mot graphique de
    chaque token), comme les versets de data/he (sans la couche des lemmes)."""
    words = pointed_words(text)
    segs = segmenter.segment_words([consonantal(w) for w in words])
    tokens, graphic = [], []
    for k, (word, parts) in enumerate(zip(words, segs)):
        for piece in split_pointed(word, parts):
            tokens.append(piece)
            graphic.append(str(k))
    return Verse(*_ref(ref), {"t": text, "w": " ".join(tokens), "g": " ".join(graphic)})


GREEK_KEEP = "᾿’'ʼ"            # marques d'élision gardées (ἀπ᾿)


def greek_verse(text: str, ref: str = "B.1.1") -> Verse:
    """Texte grec saisi -> Verse aux couches t, w (un token par mot, sans
    ponctuation, élision gardée) et g, comme les versets de data/lxx."""
    words = []
    for w in text.split():
        w = "".join(c for c in unicodedata.normalize("NFC", w)
                    if unicodedata.category(c)[0] in "LM" or c in GREEK_KEEP)
        if any(unicodedata.category(c)[0] == "L" for c in w):
            words.append(w)
    return Verse(*_ref(ref), {"t": text, "w": " ".join(words),
                              "g": " ".join(str(k) for k in range(len(words)))})
