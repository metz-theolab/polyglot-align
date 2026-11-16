"""Résultat d'un alignement et format des fichiers results/<nom>/<passage>.jsonl.

Seul endroit du code qui écrit et lit ce format (alignement, évaluation,
`polyglot-align show`, non-régression). Une ligne par verset :

  {"ref": "Gen.1.1", "src": [...], "tgt": [...], "links": {"inter": "0-0 1-1 ...", ...}}

- ref : référence hébraïque ; ref_lxx n'est présent que si le verset LXX
  apparié a un autre numéro (ex. "ref": "Ps.23.1", "ref_lxx": "Ps.22.1") ;
- src, tgt : tokens montrés par l'aligneur, dans l'ordre de l'export (indices
  reliables au gold par la couche g) ;
- links : une entrée par méthode, liens "i-j" (i : hébreu, j : grec) triés,
  séparés par des espaces (format « Pharaoh », celui d'eflomal et de fast_align) ;
- autres champs : informations propres à l'aligneur (ex. llm_table).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class VerseAlignment:
    """Résultat de l'alignement d'un verset, renvoyé par Aligner.align."""
    src: list                    # tokens hébreux montrés (un par token de la couche)
    tgt: list                    # tokens grecs montrés
    links: dict                  # méthode -> [(i, j), ...] (i : hébreu, j : grec)
    extra: dict = field(default_factory=dict)  # informations propres à l'aligneur (ex. llm_table)


def format_links(pairs) -> str:
    """[(1, 2), (0, 0)] -> "0-0 1-2" (liens triés)."""
    return " ".join(f"{a}-{b}" for a, b in sorted(pairs))


def parse_links(raw: str) -> list:
    """"0-0 1-2" -> [(0, 0), (1, 2)], dans l'ordre de la chaîne."""
    return [tuple(map(int, p.split("-"))) for p in raw.split()]


@dataclass
class AlignmentRecord:
    """Une ligne du JSONL : un verset aligné, avec sa référence."""
    ref: str                     # référence hébraïque, "Gen.1.1"
    src: list
    tgt: list
    links: dict                  # méthode -> [(i, j), ...]
    ref_lxx: str = None          # référence LXX si elle diffère de ref
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_alignment(cls, hv, gv, res: VerseAlignment) -> "AlignmentRecord":
        """Ligne du verset hébreu hv aligné avec le verset grec gv (corpus.Verse)."""
        return cls(hv.ref, res.src, res.tgt, res.links,
                   ref_lxx=gv.ref if gv.key != hv.key else None, extra=res.extra)

    @property
    def key(self) -> str:
        """Verset hébreu sans le livre : "1.1"."""
        return self.ref.split(".", 1)[1]

    @property
    def lxx_key(self) -> str:
        """Verset LXX apparié, sans le livre (par défaut, même numéro)."""
        return (self.ref_lxx or self.ref).split(".", 1)[1]

    def to_json(self) -> str:
        ref_lxx = {"ref_lxx": self.ref_lxx} if self.ref_lxx else {}
        links = {m: format_links(p) for m, p in self.links.items()}
        return json.dumps({"ref": self.ref, **ref_lxx, "src": self.src, "tgt": self.tgt,
                           "links": links, **self.extra}, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "AlignmentRecord":
        d = json.loads(line)
        links = {m: parse_links(raw) for m, raw in d.pop("links").items()}
        return cls(d.pop("ref"), d.pop("src"), d.pop("tgt"), links,
                   ref_lxx=d.pop("ref_lxx", None), extra=d)


def read_jsonl(path) -> Iterator[AlignmentRecord]:
    """Les versets d'un fichier JSONL, dans l'ordre du fichier."""
    with open(Path(path), encoding="utf-8") as f:
        for line in f:
            yield AlignmentRecord.from_json(line)
