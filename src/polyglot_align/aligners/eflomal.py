"""Aligneur statistique eflomal (Östling & Tiedemann 2016), voir DECISIONS.md
« Aligneur statistique eflomal ».

eflomal n'aligne pas verset par verset : il apprend sur tout le corpus BHSA / LXX
(cooccurrences des mots, sans aucun lien du gold). `fit` aligne donc une fois
toutes les paires de versets reçues (aujourd'hui toute la table d'équivalence,
DataStore.table_pairs : seulement des versets qui se correspondent, Josué et
Juges A compris) et garde les liens ; `align(hv, gv)` renvoie ensuite ceux du
verset demandé.

Deux symétrisations des deux sens (hébreu → grec, grec → hébreu) :
    inter : intersection (précision)
    gdfa  : grow-diag-final-and (rappel)

Installation : pip install eflomal (à lancer à la main dans le venv).
"""
import logging
import tempfile
from pathlib import Path

from polyglot_align.aligners.base import Aligner
from polyglot_align.alignment import VerseAlignment, parse_links

log = logging.getLogger(__name__)


def grow_diag_final_and(fwd: set, rev: set) -> set:
    """Symétrisation grow-diag-final-and (Koehn et al. 2005), comme `atools`.
    Part de l'intersection ; ajoute les liens voisins (diagonales comprises) de
    l'union qui touchent un mot encore non aligné ; puis (final-and) les liens
    de chaque sens dont les deux mots sont non alignés."""
    links = fwd & rev
    union = fwd | rev
    src_done = {i for i, _ in links}
    tgt_done = {j for _, j in links}
    neighbours = [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    added = True
    while added:
        added = False
        for i, j in sorted(links):
            for di, dj in neighbours:
                p = (i + di, j + dj)
                if p in union and p not in links and (p[0] not in src_done or p[1] not in tgt_done):
                    links.add(p)
                    src_done.add(p[0])
                    tgt_done.add(p[1])
                    added = True
    for direction in (fwd, rev):
        for i, j in sorted(direction):
            if i not in src_done and j not in tgt_done:
                links.add((i, j))
                src_done.add(i)
                tgt_done.add(j)
    return links


class EflomalAligner(Aligner):
    """eflomal sur la couche `layer` (w, g ou l), tokens normalisés comme pour
    SimAlign (normalize.py)."""

    name = "eflomal"
    PARAMS = {}                  # aucune option propre

    def __init__(self, layer="w", hebrew="unvocalized", greek="accented", target="lxx"):
        super().__init__(layer, hebrew, greek, target)
        self.links = {}          # (livre hébreu, livre grec, "ch.vs") -> {"inter": set, "gdfa": set}

    def tokens(self, hv, gv):
        """Tokens montrés et donnés à eflomal ; un token ne doit pas contenir
        d'espace (norm_heb rend בית_אל en « בית אל » : on remet le _)."""
        src, tgt = self.normalized_tokens(hv, gv)
        return [t.replace(" ", "_") for t in src], [t.replace(" ", "_") for t in tgt]

    def fit(self, pairs) -> None:
        """Aligne ensemble toutes les paires de versets (hébreu, grec) reçues."""
        from eflomal import Aligner as Eflomal   # import tardif : paquet optionnel
        keys, src_lines, tgt_lines = [], [], []
        for hv, gv in pairs:
            src, tgt = self.tokens(hv, gv)
            if src and tgt and all(src) and all(tgt):
                keys.append((hv.book, gv.book, hv.key))
                src_lines.append(" ".join(src) + "\n")
                tgt_lines.append(" ".join(tgt) + "\n")
            else:
                self.stats["versets vides ignorés"] += 1
        log.info("eflomal : apprentissage sur %d versets", len(keys))
        with tempfile.TemporaryDirectory() as tmp:
            fwd_path, rev_path = Path(tmp) / "fwd", Path(tmp) / "rev"
            Eflomal().align(src_lines, tgt_lines, links_filename_fwd=str(fwd_path),
                            links_filename_rev=str(rev_path), quiet=False)
            fwd_lines = fwd_path.read_text(encoding="utf-8").splitlines()
            rev_lines = rev_path.read_text(encoding="utf-8").splitlines()
        for key, f, r in zip(keys, fwd_lines, rev_lines, strict=True):
            fwd, rev = set(parse_links(f)), set(parse_links(r))
            self.links[key] = {"inter": fwd & rev, "gdfa": grow_diag_final_and(fwd, rev)}
        self.stats["versets appris"] = len(keys)

    def align(self, hv, gv) -> VerseAlignment:
        src, tgt = self.tokens(hv, gv)
        links = self.links.get((hv.book, gv.book, hv.key))
        if links is None:
            if not self.links:
                raise RuntimeError("EflomalAligner.align appelé avant fit")
            links = {"inter": set(), "gdfa": set()}   # verset vide, non appris
        return VerseAlignment(src, tgt, links)
