"""Aligneur SimAlign (Jalili Sabet et al. 2020)."""
from polyglot_align.aligners.base import Aligner
from polyglot_align.alignment import VerseAlignment
from polyglot_align.normalize import norm_grc, norm_heb


class SimAlignAligner(Aligner):
    """SimAlign (Jalili Sabet et al. 2020) sur un modèle à embeddings
    (mBERT, XLM-R, Glot500…). Reçoit les tokens normalisés (normalize.py)."""

    def __init__(self, model="bert", layer_nn=8, methods="mai", device="cpu",
                 layer="w", greek_accents=True, hebrew_vocalization=False):
        super().__init__(layer)
        self.greek_accents = greek_accents
        self.hebrew_vocalization = hebrew_vocalization
        from simalign import SentenceAligner  # import tardif (lourd)
        self.model = SentenceAligner(model=model, token_type="bpe", matching_methods=methods,
                                     layer=layer_nn, device=device)

    def align(self, hv, gv) -> VerseAlignment:
        src = [norm_heb(t, self.hebrew_vocalization) for t in hv.tokens(self.layer)]
        tgt = [norm_grc(t, self.greek_accents) for t in gv.tokens(self.layer)]
        return VerseAlignment(src, tgt, self.model.get_word_aligns(src, tgt))
