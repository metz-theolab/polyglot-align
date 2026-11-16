"""Configuration d'une expérience : lecture et vérification du YAML.

Format (voir DECISIONS.md « Paquet Python installable… », choix « Config par
aligneur ») :

    name: glot500_vocalized          # dossier des résultats : results/<name>/
    passages:
      - {book: Gen}                  # tout le livre
      - {book: Judg, lxx_book: JudgA}
      - {book: Gen, only: Gen.1}     # un chapitre (ou un verset)
    tokens: w                        # w = mots BHSA, g = mots graphiques, l = lemmes
    hebrew: vocalized                # pointed | vocalized | unvocalized
    greek: unaccented                # accented | unaccented
    aligner:                         # options propres à l'aligneur
      type: simalign                 # simalign | eflomal | llm (registre : aligners/__init__.py)
      model: cis-lmu/glot500-base
      bert_layer: 8

Options communes (tokens, hebrew, greek) : comprises par tous les aligneurs.
Options de la section `aligner` : déclarées par la classe de l'aligneur
(Aligner.PARAMS, avec leurs valeurs par défaut) et vérifiées par elle
(Aligner.check_params).

Une erreur de configuration (clé inconnue, valeur invalide, option manquante)
arrête le programme dès le démarrage, avant tout calcul.

L'ancien format plat (aligner: simalign, model, layer, llm_model,
greek_accents, hebrew_vocalization…), celui des résultats déjà produits et de
tests/reference/, est lu et converti par upgrade_legacy.
"""
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

from polyglot_align.aligners import ALIGNERS
from polyglot_align.normalize import GREEK, HEBREW

TOKENS = ("w", "g", "l")


@dataclass
class Passage:
    """Un passage à aligner : un livre, éventuellement limité à `only`."""
    book: str                    # livre hébreu (data/he/<book>.json)
    lxx_book: str = None         # livre grec s'il diffère (JoshA, JudgA)
    only: str = None             # chapitre ou verset, ex. "Gen.1" ; None = tout le livre

    def __post_init__(self):
        self.lxx_book = self.lxx_book or self.book

    @property
    def label(self) -> str:
        """Nom des fichiers de résultats du passage (Gen.1.jsonl, JudgA.jsonl…)."""
        return self.only or self.lxx_book


# --- ancien format plat ------------------------------------------------------

# options plates de l'ancien format -> option de la section `aligner`, par aligneur
LEGACY_PARAMS = {
    "simalign": {"model": "model", "layer": "bert_layer", "methods": "methods", "device": "device"},
    "llm": {"llm_model": "model", "llm_url": "url", "llm_think": "think"},
    "eflomal": {},
}
LEGACY_KEYS = ({k for m in LEGACY_PARAMS.values() for k in m}
               | {"greek_accents", "hebrew_vocalization", "llm_hebrew"})


def is_legacy(raw: dict) -> bool:
    return isinstance(raw.get("aligner"), str) or bool(LEGACY_KEYS & set(raw))


def upgrade_legacy(raw: dict) -> dict:
    """Ancien format plat -> format actuel, à l'identique de ce que recevait
    l'aligneur :
    - SimAlign, eflomal : hebrew_vocalization (défaut faux) -> hebrew
      vocalized / unvocalized ; greek_accents (défaut vrai) -> greek
      accented / unaccented ;
    - LLM : llm_hebrew (défaut pointed) -> hebrew ; greek = accented (le LLM
      recevait toujours le grec accentué, greek_accents était ignoré) ;
    - options des autres aligneurs (présentes mais ignorées) : retirées."""
    raw = dict(raw)
    kind = raw.pop("aligner", "simalign")
    accents = raw.pop("greek_accents", True)
    vocalization = raw.pop("hebrew_vocalization", False)
    llm_hebrew = raw.pop("llm_hebrew", "pointed")
    section = {"type": kind}
    for aligner, mapping in LEGACY_PARAMS.items():
        for old, new in mapping.items():
            if old in raw:
                value = raw.pop(old)
                if aligner == kind:
                    section[new] = value
    if kind == "llm":
        raw["hebrew"], raw["greek"] = llm_hebrew, "accented"
    else:
        raw["hebrew"] = "vocalized" if vocalization else "unvocalized"
        raw["greek"] = "accented" if accents else "unaccented"
    raw["aligner"] = section
    return raw


# --- configuration -----------------------------------------------------------


@dataclass
class Config:
    name: str                                     # dossier des résultats : results/<name>/
    passages: list = field(default_factory=list)  # liste de Passage

    # texte donné à l'aligneur (options communes à tous les aligneurs)
    tokens: str = "w"             # w = mots BHSA (בְּ רֵאשִׁית), g = mots graphiques (בְּרֵאשִׁית), l = lemmes
    hebrew: str = "unvocalized"   # pointed = tel qu'exporté, vocalized = voyelles sans accents,
                                  # unvocalized = consonantique
    greek: str = "accented"       # accented, unaccented = accents et esprits retirés, minuscules

    # aligneur : {"type": ..., options propres complétées par leurs valeurs par défaut}
    aligner: dict = field(default_factory=lambda: {"type": "simalign"})

    @classmethod
    def from_yaml(cls, path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(raw, source=path)

    @classmethod
    def from_dict(cls, raw: dict, source="config", check: bool = True) -> "Config":
        """check=False : sans vérification (lecture de résultats anciens par report.py)."""
        if is_legacy(raw):
            raw = upgrade_legacy(raw)
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"{source} : option(s) inconnue(s) : {', '.join(sorted(unknown))}")
        raw = dict(raw)
        raw["passages"] = [Passage(**p) for p in raw.get("passages", [])]
        section = raw.get("aligner", {"type": "simalign"})
        if not isinstance(section, dict) or "type" not in section:
            raise ValueError(f"{source} : `aligner` doit être une section avec `type` "
                             f"({', '.join(ALIGNERS)})")
        if section["type"] in ALIGNERS:   # valeurs par défaut de l'aligneur
            section = {"type": section["type"], **ALIGNERS[section["type"]].PARAMS, **section}
        raw["aligner"] = section
        cfg = cls(**raw)
        if check:
            cfg.check(source)
        return cfg

    @property
    def aligner_type(self) -> str:
        return self.aligner["type"]

    @property
    def aligner_params(self) -> dict:
        """Options propres à l'aligneur, sans `type`."""
        return {k: v for k, v in self.aligner.items() if k != "type"}

    def check(self, source="config") -> None:
        """Vérifie la cohérence des options."""
        problems = []
        if not self.passages:
            problems.append("aucun passage")
        if self.tokens not in TOKENS:
            problems.append(f"tokens = {self.tokens!r} (attendu : w, g ou l)")
        if self.hebrew not in HEBREW:
            problems.append(f"hebrew = {self.hebrew!r} (attendu : {', '.join(HEBREW)})")
        if self.greek not in GREEK:
            problems.append(f"greek = {self.greek!r} (attendu : {', '.join(GREEK)})")
        cls = ALIGNERS.get(self.aligner_type)
        if cls is None:
            problems.append(f"aligner type = {self.aligner_type!r} (attendu : {', '.join(ALIGNERS)})")
        else:
            unknown = set(self.aligner_params) - set(cls.PARAMS)
            if unknown:
                problems.append(f"aligner {self.aligner_type} : option(s) inconnue(s) : "
                                f"{', '.join(sorted(unknown))} (possibles : {', '.join(cls.PARAMS) or 'aucune'})")
            else:
                problems += cls.check_params(self.aligner_params)
        if problems:
            raise ValueError(f"{source} : " + " ; ".join(problems))

    def flat(self) -> dict:
        """Options à plat, sans le nom, pour les libellés et les comparaisons :
        {"passages": …, "tokens": …, "hebrew": …, "greek": …, "aligner.type": …,
        "aligner.model": …}."""
        d = self.to_dict()
        d.pop("name")
        aligner = d.pop("aligner")
        return d | {f"aligner.{k}": v for k, v in aligner.items()}

    def differences(self, other: "Config") -> list:
        """Options (à plat) dont la valeur diffère entre self et other."""
        a, b = self.flat(), other.flat()
        return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))

    def to_dict(self) -> dict:
        """Options sous forme de dictionnaire (format actuel), passages compris."""
        return {"name": self.name,
                "passages": [{k: v for k, v in vars(p).items()} for p in self.passages],
                "tokens": self.tokens, "hebrew": self.hebrew, "greek": self.greek,
                "aligner": dict(self.aligner)}
