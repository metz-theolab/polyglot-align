"""Aligner un texte hébreu et un texte grec saisis (app de test).

Voir DECISIONS.md « align("texte A", "texte B") » et decisions-app.md « Trois
algorithmes dans l'app ». Un texte saisi est un bloc, traité comme un seul
verset, même s'il en couvre plusieurs. L'hébreu est découpé en mots BHSA
(segment.py) ; le segmenteur est partagé par tous les algorithmes.

Trois algorithmes, même interface (align, align_many -> TextAlignment) :

    TextAligner          eflomal : la paire saisie est ajoutée aux 22 489
                         paires de la table et eflomal apprend sur l'ensemble
    SimAlignTextAligner  SimAlign (Glot500 par défaut), sans apprentissage
    LLMTextAligner       LLM servi par Ollama (Gemma 4 12B par défaut)

Deux niveaux de liens pour tous : `sure` (liens sûrs) et `all` (sûrs +
probables ; sure est inclus dans all). `methods` dit à quoi ils
correspondent : eflomal inter / gdfa, SimAlign inter (argmax) / itermax, LLM
un seul niveau. Les résultats d'eflomal et du LLM varient légèrement d'un
appel à l'autre (non déterministes).

    aligner = TextAligner()
    res = aligner.align("בְּרֵאשִׁית בָּרָא אֱלֹהִים", "ἐν ἀρχῇ ἐποίησεν ὁ θεὸς")
    res.pairs("sure")         # [("בְּ", "ἐν"), ("רֵאשִׁית", "ἀρχῇ"), …]
    res.to_dict()             # pour l'API (JSON)
"""
import logging
from dataclasses import dataclass, field

from polyglot_align.aligners.eflomal import EflomalAligner
from polyglot_align.corpus import Verse
from polyglot_align.segment import CombinedSegmenter, Segmenter, greek_verse, hebrew_verse
from polyglot_align.store import DataStore

log = logging.getLogger(__name__)

LEVELS = ("sure", "all")


@dataclass
class TextAlignment:
    """Alignement d'une paire de textes saisis : liens (i, j) entre les tokens
    w du texte hébreu (i) et du texte grec (j), par niveau (sure, all)."""
    hebrew: Verse
    greek: Verse
    links: dict                  # "sure" / "all" -> [(i, j), ...], triés ; sure ⊆ all
    algorithm: str = "eflomal"
    methods: dict = field(default_factory=lambda: {"sure": "inter", "all": "gdfa"})
    notes: list = field(default_factory=list)   # ex. réponse du LLM tronquée

    def pairs(self, level: str = "sure") -> list:
        """[(token hébreu, token grec)] des liens du niveau `level`."""
        he, gr = self.hebrew.tokens("w"), self.greek.tokens("w")
        return [(he[i], gr[j]) for i, j in self.links[level]]

    def by_graphic_word(self, level: str = "sure") -> list:
        """Pour chaque mot graphique hébreu : ses tokens et les mots grecs
        reliés à l'un d'eux, dans l'ordre du grec (affichage)."""
        he, gr = self.hebrew.tokens("w"), self.greek.tokens("w")
        words = {}
        for i, (tok, k) in enumerate(zip(he, self.hebrew.graphic_numbers())):
            w = words.setdefault(k, {"hebrew": "", "tokens": [], "greek": set()})
            w["hebrew"] += tok
            w["tokens"].append(tok)
            w["greek"].update(j for a, j in self.links[level] if a == i)
        return [{"hebrew": w["hebrew"], "tokens": w["tokens"], "greek": [gr[j] for j in sorted(w["greek"])]}
                for w in words.values()]

    def to_dict(self) -> dict:
        """Forme JSON (API) : textes, tokens, numéros de mots graphiques, liens."""
        def side(v: Verse) -> dict:
            return {"text": v.layers["t"], "tokens": v.tokens("w"),
                    "graphic": [int(k) for k in v.graphic_numbers()]}
        return {"hebrew": side(self.hebrew), "greek": side(self.greek),
                "links": {lv: [list(p) for p in self.links[lv]] for lv in LEVELS},
                "algorithm": self.algorithm, "methods": dict(self.methods), "notes": list(self.notes)}


def levels(sure, probable=()) -> dict:
    """{"sure": liens sûrs, "all": sûrs + probables}, triés."""
    sure = set(map(tuple, sure))
    return {"sure": sorted(sure), "all": sorted(sure | set(map(tuple, probable)))}


class BaseTextAligner:
    """Partie commune : segmentation des textes saisis en versets."""

    name = None
    methods = {}

    def __init__(self, segmenter: Segmenter, hebrew: str, greek: str):
        self.segmenter, self.hebrew, self.greek = segmenter, hebrew, greek

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
        raise NotImplementedError

    def align(self, hebrew_text: str, greek_text: str) -> TextAlignment:
        """Aligne un texte hébreu et un texte grec saisis."""
        return self.align_many([(hebrew_text, greek_text)])[0]

    def result(self, hv, gv, links: dict, notes=()) -> TextAlignment:
        return TextAlignment(hv, gv, links, self.name, dict(self.methods), list(notes))


class TextAligner(BaseTextAligner):
    """eflomal, appris sur toute la table des versets plus les paires saisies.

    store : données (data/) ; segmenter : segmentation de l'hébreu (par défaut
    CombinedSegmenter : table BHSA + dictabert-seg) ; hebrew, greek :
    normalisation donnée à eflomal (par défaut celle de la meilleure
    expérience, eflomal_unvocalized : F1 inter 95,2 %)."""

    name = "eflomal"
    methods = {"sure": "inter", "all": "gdfa"}

    def __init__(self, store: DataStore = None, segmenter: Segmenter = None,
                 hebrew: str = "unvocalized", greek: str = "unaccented"):
        self.store = store or DataStore("data")
        super().__init__(segmenter or CombinedSegmenter.from_store(self.store), hebrew, greek)
        self.table_pairs = list(self.store.table_pairs())   # données d'apprentissage

    def align_many(self, pairs: list) -> list:
        """[(texte hébreu, texte grec), …] -> [TextAlignment], avec un seul
        apprentissage d'eflomal pour toutes les paires."""
        verses = self.verses(pairs)
        aligner = EflomalAligner(layer="w", hebrew=self.hebrew, greek=self.greek)
        log.info("eflomal : apprentissage sur la table et %d paire(s) saisie(s)", len(verses))
        aligner.fit(self.table_pairs + verses)
        out = []
        for hv, gv in verses:
            res = aligner.align(hv, gv)
            out.append(self.result(hv, gv, levels(res.links["inter"], res.links["gdfa"])))
        return out


class SimAlignTextAligner(BaseTextAligner):
    """SimAlign sur un modèle à plongements, sans apprentissage. Par défaut
    Glot500, couche 8, hébreu vocalisé (glot500_vocalized, meilleur modèle à
    plongements : F1 76,6 % sur toute la Bible). Liens sûrs : inter (argmax) ;
    probables : ce qu'itermax ajoute."""

    name = "simalign"
    methods = {"sure": "inter (argmax)", "all": "itermax"}

    def __init__(self, segmenter: Segmenter, model: str = "cis-lmu/glot500-base", bert_layer: int = 8,
                 hebrew: str = "vocalized", greek: str = "unaccented", device: str = "cpu"):
        from polyglot_align.aligners.simalign import SimAlignAligner   # torch, modèle : lourd
        super().__init__(segmenter, hebrew, greek)
        self.model = model
        self.aligner = SimAlignAligner(model=model, bert_layer=bert_layer, methods="ai", device=device,
                                       layer="w", hebrew=hebrew, greek=greek)

    def align_many(self, pairs: list) -> list:
        out = []
        for hv, gv in self.verses(pairs):
            res = self.aligner.align(hv, gv)
            out.append(self.result(hv, gv, levels(res.links["inter"], res.links["itermax"])))
        return out


class LLMTextAligner(BaseTextAligner):
    """LLM servi par Ollama (Gemma 4 12B par défaut ; gemma4_unvocalized,
    Genèse : F1 90,7 %), hébreu consonantique, grec accentué. Un seul niveau
    de liens (sure = all). Réponse tronquée ou absente : signalée dans notes."""

    name = "llm"

    def __init__(self, segmenter: Segmenter, model: str = "gemma4:12b", url: str = "http://localhost:11434",
                 hebrew: str = "unvocalized", greek: str = "accented", num_predict: int = 4096):
        from polyglot_align.aligners.llm import OllamaAligner
        super().__init__(segmenter, hebrew, greek)
        self.model, self.url = model, url
        self.methods = {"sure": model, "all": model}
        self.aligner = OllamaAligner(model, url, num_predict=num_predict, layer="w",
                                     hebrew=hebrew, greek=greek)

    def align_many(self, pairs: list) -> list:
        out = []
        for hv, gv in self.verses(pairs):
            before = dict(self.aligner.stats)
            res = self.aligner.align(hv, gv)
            new = lambda key: self.aligner.stats[key] - before.get(key, 0)
            notes = []
            if new("reponses_tronquees"):
                notes.append("the model's answer was cut off (repetition loop): only complete rows were kept")
            if new("versets_sans_reponse"):
                notes.append("the model gave no usable answer: no link")
            out.append(self.result(hv, gv, levels(res.links["llm"]), notes))
        return out
