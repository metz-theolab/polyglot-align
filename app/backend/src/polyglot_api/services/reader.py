"""Reader : lecture des alignements déjà calculés (results/<nom>/), l'hébreu en
pivot (decisions-app.md, « Lecteur des textes alignés »).

- résultats publiés : liste blanche (réglage `reader_corpora`), chacun décrit
  par sa config (results/<nom>/config.yaml : cible lxx ou syr, couche de tokens) ;
- pivot : mots hébreux séparés par des espaces (Verse.spaced_words) ; les
  tokens hébreux de chaque résultat (w : mots BHSA, t : mots séparés par des
  espaces) y sont rattachés, les liens sont donnés mot pivot ↔ token cible ;
- un seul niveau de liens (réglage `reader_method`, gdfa) ;
- LXX : verdict du gold par mot pivot, lu dans le CSV de relecture ;
- un fichier de résultats (un livre) est lu à la demande et gardé en cache
  (les `reader_cache` derniers lus).
"""
import csv
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import yaml
from polyglot_align.alignment import read_jsonl
from polyglot_align.config import Config
from polyglot_align.corpus import ref_key
from polyglot_align.store import DataStore

log = logging.getLogger(__name__)

LANGUAGES = {"lxx": ("grc", "ltr", "LXX"), "syr": ("syc", "rtl", "Peshitta")}

# verdicts du CSV de relecture, du pire au meilleur : le pire donne celui du mot pivot
VERDICTS = ("faux", "non aligné", "?", "ok (minus)", "juste")


class UnknownPassage(Exception):
    """Livre ou chapitre absent."""


@dataclass
class Text:
    """Un fichier de résultats : un livre hébreu aligné avec un livre cible
    (Judg ↔ JudgA : `name` = JudgA)."""
    corpus: str
    book: str                    # livre hébreu
    name: str                    # livre cible = nom du fichier (Gen, JudgA…)


class ResultCorpus:
    """Un dossier de résultats publié."""

    def __init__(self, name: str, folder: Path):
        self.name, self.folder = name, folder
        path = folder / "config.yaml"
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg = Config.from_dict(raw, source=path, check=False)    # résultats anciens : format plat
        self.target, self.layer = cfg.target, cfg.tokens
        self.aligner = cfg.aligner_type
        self.language, self.direction, target_label = LANGUAGES[self.target]
        self.label = f"{target_label} — {self.aligner}"
        self.texts = [Text(name, p.book, p.lxx_book) for p in cfg.passages
                      if p.only is None and (folder / f"{p.lxx_book}.jsonl").exists()]

    @property
    def gold(self) -> bool:
        return self.target == "lxx"


class Reader:
    def __init__(self, store: DataStore, results_dir, corpora: list, method: str = "gdfa",
                 cache: int = 16):
        self.store, self.method, self.cache_size = store, method, cache
        self.corpora = {}
        for name in corpora:
            folder = Path(results_dir) / name
            if not (folder / "config.yaml").exists():
                log.warning("résultats %s absents (%s) : non publiés", name, folder)
                continue
            self.corpora[name] = ResultCorpus(name, folder)
        self._cache = OrderedDict()      # (corpus, texte) -> {clé hébraïque: verset}
        self._lock = threading.Lock()

    # --- catalogue -----------------------------------------------------------

    def books(self) -> list:
        """[(livre hébreu, [chapitres], [Text])], dans l'ordre biblique des
        configs (un livre absent d'une config est inséré après son prédécesseur
        dans une autre)."""
        order = []
        for c in self.corpora.values():
            prev = None
            for t in c.texts:
                if t.book not in order:
                    order.insert(order.index(prev) + 1 if prev else len(order), t.book)
                prev = t.book
        out = []
        for book in order:
            chapters = list(dict.fromkeys(k.split(".")[0] for k in self.store.corpus("he", book).keys()))
            texts = [t for c in self.corpora.values() for t in c.texts if t.book == book]
            out.append((book, chapters, texts))
        return out

    # --- un chapitre ---------------------------------------------------------

    def chapter(self, book: str, chapter: str, corpora: list | None = None) -> list:
        """Versets du chapitre hébreu : [{ref, words, targets}] (voir schemas.ReaderVerse)."""
        if not any(t.book == book for c in self.corpora.values() for t in c.texts):
            raise UnknownPassage(f"unknown book: {book}")    # aussi : pas de chemin hors de data/
        he = self.store.corpus("he", book)
        keys = sorted((k for k in he.keys() if k.split(".")[0] == chapter), key=ref_key)
        if not keys:
            raise UnknownPassage(f"unknown chapter: {book} {chapter}")
        names = [n for n in (corpora or self.corpora) if n in self.corpora]
        texts = [t for n in names for t in self.corpora[n].texts if t.book == book]
        loaded = [(t, self._load(t)) for t in texts]
        verses = []
        for key in keys:
            hv = he[key]
            groups = hv.spaced_words()
            tokens = hv.tokens("t")
            words = [{"text": " ".join(tokens[i] for i in t), "graphic": bool(g)} for t, g in groups]
            targets = [self._target(t, data[key], hv, groups)
                       for t, data in loaded if key in data]
            verses.append({"ref": hv.ref, "words": words, "targets": targets})
        return verses

    def _target(self, text: Text, item: tuple, hv, groups) -> dict:
        record, verdicts = item
        corpus = self.corpora[text.corpus]
        word_of = self._pivot(corpus.layer, hv, groups)
        tv = self.store.corpus(corpus.target, text.name)[record.lxx_key]
        tokens = tv.tokens(corpus.layer)
        links = sorted({(word_of[i], j) for i, j in record.links[self.method]})
        out = {"corpus": text.corpus, "text": text.name, "ref": tv.ref, "tokens": tokens,
               "links": links, "verdicts": None}
        if verdicts is not None:
            worst = [None] * len(groups)
            for i, v in verdicts.items():
                w = word_of[i]
                if v in VERDICTS and (worst[w] is None or VERDICTS.index(v) < VERDICTS.index(worst[w])):
                    worst[w] = v
            out["verdicts"] = worst
        return out

    @staticmethod
    def _pivot(layer: str, hv, groups) -> list:
        """Mot pivot de chaque token hébreu de la couche `layer` du résultat."""
        if layer == "t":
            return [w for w, (t, _) in enumerate(groups) for _ in t]
        word = {k: w for w, (_, g) in enumerate(groups) for k in g}
        if layer == "g":
            return [word[k] for k in dict.fromkeys(hv.graphic_numbers())]
        return [word[k] for k in hv.graphic_numbers()]       # w, l : un token par mot BHSA

    def _load(self, text: Text) -> dict:
        """{clé hébraïque "1.1": (AlignmentRecord, verdicts {n: verdict} ou None)}."""
        key = (text.corpus, text.name)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        corpus = self.corpora[text.corpus]
        records = {r.key: r for r in read_jsonl(corpus.folder / f"{text.name}.jsonl")}
        verdicts = self._verdicts(corpus.folder / f"{text.name}.csv") if corpus.gold else {}
        data = {k: (r, verdicts.get(r.ref, {}) if corpus.gold else None) for k, r in records.items()}
        with self._lock:
            self._cache[key] = data
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return data

    def _verdicts(self, path: Path) -> dict:
        """CSV de relecture (évaluation contre le gold) -> {ref: {n: verdict}}."""
        out = {}
        if not path.exists():
            return out
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                if row["methode"] == self.method and row["n"]:
                    out.setdefault(row["ref"], {})[int(row["n"])] = row["verdict"]
        return out
