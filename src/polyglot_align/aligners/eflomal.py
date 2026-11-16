"""Aligneur statistique eflomal (Östling & Tiedemann 2016), voir DECISIONS.md
« Aligneur statistique eflomal ».

eflomal n'aligne pas verset par verset : il apprend sur tout le corpus BHSA / LXX
(cooccurrences des mots, sans aucun lien du gold). `fit` aligne donc une fois
toutes les paires de versets de la table d'équivalence (corpus.VerseMap :
seulement des versets qui se correspondent, Josué et Juges A compris) et garde
les liens ; `align(hv, gv)` renvoie ensuite ceux du verset demandé.

Deux symétrisations des deux sens (hébreu → grec, grec → hébreu) :
    inter : intersection (précision)
    gdfa  : grow-diag-final-and (rappel)

Installation : pip install eflomal (à lancer à la main dans le venv).
"""
import tempfile
from pathlib import Path

from polyglot_align.aligners.base import Aligner, VerseAlignment
from polyglot_align.corpus import Corpus
from polyglot_align.normalize import norm_grc, norm_heb


def parse_pharaoh(line: str) -> set:
    """"0-0 1-2" -> {(0, 0), (1, 2)}."""
    return {tuple(map(int, p.split("-"))) for p in line.split()}


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

    def __init__(self, layer="w", greek_accents=True, hebrew_vocalization=False):
        super().__init__(layer)
        self.greek_accents = greek_accents
        self.hebrew_vocalization = hebrew_vocalization
        self.links = {}          # (livre hébreu, livre grec, "ch.vs") -> {"inter": set, "gdfa": set}

    def tokens(self, hv, gv):
        """Tokens montrés et donnés à eflomal ; un token ne doit pas contenir
        d'espace (norm_heb rend בית_אל en « בית אל » : on remet le _)."""
        src = [norm_heb(t, self.hebrew_vocalization).replace(" ", "_") for t in hv.tokens(self.layer)]
        tgt = [norm_grc(t, self.greek_accents).replace(" ", "_") for t in gv.tokens(self.layer)]
        return src, tgt

    def fit(self, verse_map, data_root) -> None:
        """Aligne toutes les paires de versets de la table (corpus.VerseMap)."""
        from eflomal import Aligner as Eflomal   # import tardif : paquet optionnel
        keys, src_lines, tgt_lines = [], [], []
        for he_book, lxx_book in verse_map.book_pairs():
            he, lxx = Corpus.load("he", he_book, data_root), Corpus.load("lxx", lxx_book, data_root)
            for he_key, lxx_key in verse_map.pairs(he_book, lxx_book):
                src, tgt = self.tokens(he[he_key], lxx[lxx_key])
                if src and tgt and all(src) and all(tgt):
                    keys.append((he_book, lxx_book, he_key))
                    src_lines.append(" ".join(src) + "\n")
                    tgt_lines.append(" ".join(tgt) + "\n")
                else:
                    self.stats["versets vides ignorés"] += 1
        print(f"eflomal : apprentissage sur {len(keys)} versets", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            fwd_path, rev_path = Path(tmp) / "fwd", Path(tmp) / "rev"
            Eflomal().align(src_lines, tgt_lines, links_filename_fwd=str(fwd_path),
                            links_filename_rev=str(rev_path), quiet=False)
            fwd_lines = fwd_path.read_text(encoding="utf-8").splitlines()
            rev_lines = rev_path.read_text(encoding="utf-8").splitlines()
        for key, f, r in zip(keys, fwd_lines, rev_lines, strict=True):
            fwd, rev = parse_pharaoh(f), parse_pharaoh(r)
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
