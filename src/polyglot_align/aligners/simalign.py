"""Aligneur SimAlign (Jalili Sabet et al. 2020)."""
from polyglot_align.aligners.base import Aligner
from polyglot_align.alignment import VerseAlignment


class SimAlignAligner(Aligner):
    """SimAlign (Jalili Sabet et al. 2020) sur un modèle à embeddings
    (mBERT, XLM-R, Glot500…). Reçoit les tokens normalisés (normalize.py)."""

    name = "simalign"
    PARAMS = {
        "model": "bert",         # bert (mBERT), xlmr, ou nom d'un modèle HuggingFace
        "bert_layer": 8,         # couche du réseau dont on prend les plongements
        "methods": "mai",        # m = mwmf, a = inter (argmax), i = itermax
        "device": "cpu",
    }

    @classmethod
    def check_params(cls, params: dict) -> list:
        problems = []
        if not set(params["methods"]) <= set("mai"):
            problems.append(f"methods = {params['methods']!r} (lettres possibles : m, a, i)")
        if not isinstance(params["bert_layer"], int):
            problems.append(f"bert_layer = {params['bert_layer']!r} (attendu : un entier)")
        return problems

    def __init__(self, model="bert", bert_layer=8, methods="mai", device="cpu",
                 layer="w", hebrew="unvocalized", greek="accented"):
        super().__init__(layer, hebrew, greek)
        from simalign import SentenceAligner  # import tardif (lourd)
        self.model = SentenceAligner(model=model, token_type="bpe", matching_methods=methods,
                                     layer=bert_layer, device=device)

    def align(self, hv, gv) -> VerseAlignment:
        src, tgt = self.normalized_tokens(hv, gv)
        return VerseAlignment(src, tgt, self.model.get_word_aligns(src, tgt))
