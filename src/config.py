"""Configuration d'une expérience : lecture et vérification du YAML.

Toutes les options et leurs valeurs par défaut sont ici, à un seul endroit.
Une erreur de configuration (clé inconnue, valeur invalide, option manquante)
arrête le programme dès le démarrage, avant tout calcul.
"""
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


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


@dataclass
class Config:
    name: str                                     # dossier des résultats : results/<name>/
    passages: list = field(default_factory=list)  # liste de Passage

    # texte donné à l'aligneur
    tokens: str = "w"             # w = mots BHSA (בְּ רֵאשִׁית), g = mots graphiques (בְּרֵאשִׁית), l = lemmes
    greek_accents: bool = True    # False = accents grecs retirés (SimAlign, eflomal)
    hebrew_vocalization: bool = False  # True = voyelles hébraïques gardées (SimAlign, eflomal)

    # aligneur
    aligner: str = "simalign"     # simalign, llm ou eflomal

    # SimAlign
    model: str = "bert"           # bert (mBERT), xlmr, ou nom d'un modèle HuggingFace
    layer: int = 8
    methods: str = "mai"          # m = mwmf, a = inter (argmax), i = itermax
    device: str = "cpu"

    # LLM (Ollama)
    llm_model: str = None
    llm_url: str = "http://localhost:11434"
    llm_think: bool = False
    llm_hebrew: str = "pointed"   # hébreu du prompt : pointed = texte d'origine (voyelles + accents),
                                  # vocalized = voyelles sans accents, unvocalized = consonantique

    @classmethod
    def from_yaml(cls, path) -> "Config":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"{path} : option(s) inconnue(s) : {', '.join(sorted(unknown))}")
        raw["passages"] = [Passage(**p) for p in raw.get("passages", [])]
        cfg = cls(**raw)
        cfg.check(path)
        return cfg

    def check(self, path="config") -> None:
        """Vérifie la cohérence des options."""
        problems = []
        if not self.passages:
            problems.append("aucun passage")
        if self.tokens not in ("w", "g", "l"):
            problems.append(f"tokens = {self.tokens!r} (attendu : w, g ou l)")
        if self.aligner not in ("simalign", "llm", "eflomal"):
            problems.append(f"aligner = {self.aligner!r} (attendu : simalign, llm ou eflomal)")
        if self.aligner == "llm" and not self.llm_model:
            problems.append("aligner = llm mais llm_model n'est pas donné")
        if self.llm_hebrew not in ("pointed", "vocalized", "unvocalized"):
            problems.append(f"llm_hebrew = {self.llm_hebrew!r} (attendu : pointed, vocalized ou unvocalized)")
        if self.aligner == "simalign" and not set(self.methods) <= set("mai"):
            problems.append(f"methods = {self.methods!r} (lettres possibles : m, a, i)")
        if problems:
            raise ValueError(f"{path} : " + " ; ".join(problems))
