"""Aligner un texte hébreu et un texte grec saisis, avec eflomal (app de test).

Voir DECISIONS.md « align("texte A", "texte B") ». eflomal n'aligne pas une
phrase isolée : la paire saisie est ajoutée aux 22 489 paires de la table des
versets, et eflomal apprend sur l'ensemble. Un texte saisi est un bloc,
traité comme un seul verset, même s'il en couvre plusieurs.

    aligner = TextAligner()                     # données et segmenteur chargés une fois
    res = aligner.align("בְּרֵאשִׁית בָּרָא אֱלֹהִים", "ἐν ἀρχῇ ἐποίησεν ὁ θεὸς")
    res.pairs("inter")        # [("בְּ", "ἐν"), ("רֵאשִׁית", "ἀρχῇ"), …]
    res.to_dict()             # pour l'API (JSON)

Les deux symétrisations sont renvoyées : `inter` (liens communs aux deux
sens, sûrs) et `gdfa` (inter + liens d'un seul sens) ; inter est inclus dans
gdfa. Le résultat varie légèrement d'un appel à l'autre (eflomal n'est pas
déterministe).
"""
import logging
from dataclasses import dataclass

from polyglot_align.aligners.eflomal import EflomalAligner
from polyglot_align.corpus import Verse
from polyglot_align.segment import CombinedSegmenter, Segmenter, greek_verse, hebrew_verse
from polyglot_align.store import DataStore

log = logging.getLogger(__name__)

METHODS = ("inter", "gdfa")


@dataclass
class TextAlignment:
    """Alignement d'une paire de textes saisis : liens (i, j) entre les tokens
    w du texte hébreu (i) et du texte grec (j), par symétrisation."""
    hebrew: Verse
    greek: Verse
    links: dict                  # "inter" / "gdfa" -> [(i, j), ...], triés

    def pairs(self, method: str = "inter") -> list:
        """[(token hébreu, token grec)] des liens de `method`."""
        he, gr = self.hebrew.tokens("w"), self.greek.tokens("w")
        return [(he[i], gr[j]) for i, j in self.links[method]]

    def by_graphic_word(self, method: str = "inter") -> list:
        """Pour chaque mot graphique hébreu : ses tokens et les mots grecs
        reliés à l'un d'eux, dans l'ordre du grec (affichage)."""
        he, gr = self.hebrew.tokens("w"), self.greek.tokens("w")
        numbers = self.hebrew.graphic_numbers()
        words = {}
        for i, (tok, k) in enumerate(zip(he, numbers)):
            w = words.setdefault(k, {"hebrew": "", "tokens": [], "greek": set()})
            w["hebrew"] += tok
            w["tokens"].append(tok)
            w["greek"].update(j for a, j in self.links[method] if a == i)
        return [{"hebrew": w["hebrew"], "tokens": w["tokens"], "greek": [gr[j] for j in sorted(w["greek"])]}
                for w in words.values()]

    def to_dict(self) -> dict:
        """Forme JSON (API) : textes, tokens, numéros de mots graphiques, liens."""
        def side(v: Verse) -> dict:
            return {"text": v.layers["t"], "tokens": v.tokens("w"),
                    "graphic": [int(k) for k in v.graphic_numbers()]}
        return {"hebrew": side(self.hebrew), "greek": side(self.greek),
                "links": {m: [list(p) for p in self.links[m]] for m in METHODS}}


class TextAligner:
    """Aligne des paires de textes saisis (hébreu, grec) avec eflomal, appris
    sur toute la table des versets plus les paires saisies.

    store : données (data/) ; segmenter : segmentation de l'hébreu
    (par défaut CombinedSegmenter : table BHSA + dictabert-seg) ; hebrew,
    greek : normalisation donnée à eflomal (par défaut celle de la meilleure
    expérience, eflomal_unvocalized : F1 inter 95,2 %)."""

    def __init__(self, store: DataStore = None, segmenter: Segmenter = None,
                 hebrew: str = "unvocalized", greek: str = "unaccented"):
        self.store = store or DataStore("data")
        self.segmenter = segmenter or CombinedSegmenter.from_store(self.store)
        self.hebrew, self.greek = hebrew, greek
        self.table_pairs = list(self.store.table_pairs())   # données d'apprentissage

    def verses(self, pairs: list) -> list:
        """Textes saisis -> [(Verse hébreu, Verse grec)] (refs A.1.k / B.1.k)."""
        out = []
        for k, (he_text, gr_text) in enumerate(pairs, 1):
            hv = hebrew_verse(he_text, self.segmenter, f"A.1.{k}")
            gv = greek_verse(gr_text, f"B.1.{k}")
            if not hv.layers["w"]:
                raise ValueError(f"paire {k} : aucun mot hébreu dans le texte A")
            if not gv.layers["w"]:
                raise ValueError(f"paire {k} : aucun mot grec dans le texte B")
            out.append((hv, gv))
        return out

    def align_many(self, pairs: list) -> list:
        """[(texte hébreu, texte grec), …] -> [TextAlignment], avec un seul
        apprentissage d'eflomal pour toutes les paires."""
        verses = self.verses(pairs)
        aligner = EflomalAligner(layer="w", hebrew=self.hebrew, greek=self.greek)
        log.info("eflomal : apprentissage sur la table et %d paire(s) saisie(s)", len(verses))
        aligner.fit(self.table_pairs + verses)
        results = []
        for hv, gv in verses:
            res = aligner.align(hv, gv)
            results.append(TextAlignment(hv, gv, {m: sorted(res.links[m]) for m in METHODS}))
        return results

    def align(self, hebrew_text: str, greek_text: str) -> TextAlignment:
        """Aligne un texte hébreu et un texte grec saisis."""
        return self.align_many([(hebrew_text, greek_text)])[0]
