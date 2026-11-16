"""Aligneur par LLM local (Ollama), sur le texte (mots graphiques).

Le modèle reçoit le verset hébreu et le verset grec, mot graphique par mot
graphique, comme on le lirait, normalisés selon les options communes `hebrew`
et `greek` (par défaut pour cette classe : texte pointé et accentué, tel
qu'exporté), et répond par un tableau :
une ligne = un mot (ou groupe) hébreu et sa traduction grecque.

Le tableau est ensuite converti en liens entre tokens (couche w) : chaque
ligne est traitée comme un bloc, et ses mots sont retrouvés dans le verset par
leurs lettres (normalize.project, comme la projection du gold). Un mot
inventé par le modèle ne correspond à rien et disparaît. Tous les tokens
hébreux d'une ligne sont reliés à tous ses tokens grecs. Le tableau brut est
conservé dans le JSONL (champ "llm_table") pour la relecture.
"""
import json
import urllib.request

from polyglot_align.aligners.base import Aligner
from polyglot_align.alignment import VerseAlignment
from polyglot_align.normalize import grc_letters, heb_letters, norm_grc, norm_heb, project

PROMPT = """Align this Hebrew verse with its Greek translation (Septuagint).

Hebrew: {hb}
Greek: {gr}

Make a table: each row pairs a Hebrew word (or group of words) with the Greek
word(s) that translate it.
Rules:
- Copy the words exactly as they appear above, in the order of the Hebrew text.
- Use every Hebrew word once. Do not add, correct or complete any word.
- A Hebrew word with no Greek equivalent: row with an empty "greek".
- Greek words with no Hebrew equivalent: row with an empty "hebrew".

Answer with JSON only: {{"rows": [{{"hebrew": "...", "greek": "..."}}, ...]}}"""

SCHEMA = {  # Ollama impose ce format de réponse (sorties structurées)
    "type": "object",
    "properties": {"rows": {"type": "array", "items": {
        "type": "object",
        "properties": {"hebrew": {"type": "string"}, "greek": {"type": "string"}},
        "required": ["hebrew", "greek"]}}},
    "required": ["rows"],
}


def table_to_links(hb_tok: list, gr_tok: list, rows: list) -> list:
    """Tableau du LLM -> liens (i, j) entre tokens. Chaque ligne est un bloc :
    ses mots sont retrouvés dans le verset par leurs lettres, et tous ses tokens
    hébreux sont reliés à tous ses tokens grecs."""
    hb_row = project(hb_tok, [(k, r.get("hebrew", "")) for k, r in enumerate(rows)], heb_letters)
    gr_row = project(gr_tok, [(k, r.get("greek", "")) for k, r in enumerate(rows)], grc_letters)
    return sorted({(i, j) for i, a in enumerate(hb_row) for j, b in enumerate(gr_row)
                   if a is not None and a == b})


class OllamaAligner(Aligner):
    """LLM local (Ollama) : voit le texte en mots graphiques et répond par un
    tableau converti en liens (table_to_links)."""

    name = "llm"
    PARAMS = {
        "model": None,           # modèle Ollama, ex. gemma4:12b (obligatoire)
        "url": "http://localhost:11434",
        "think": False,          # true = le modèle « réfléchit » avant de répondre (beaucoup plus lent)
        "seed": 1,
    }

    @classmethod
    def check_params(cls, params: dict) -> list:
        return [] if params["model"] else ["aligner llm : `model` n'est pas donné (ex. gemma4:12b)"]

    def __init__(self, model: str, url: str = "http://localhost:11434", think: bool = False,
                 seed: int = 1, layer: str = "w", hebrew: str = "pointed", greek: str = "accented"):
        super().__init__(layer, hebrew, greek)
        self.model, self.url, self.think, self.seed = model, url.rstrip("/"), think, seed

    def hebrew_words(self, hv) -> list:
        """Mots graphiques hébreux du prompt, normalisés selon `hebrew`
        (pointed : texte tel qu'exporté)."""
        return [norm_heb(w, self.hebrew) for w in hv.graphic_words(self.layer)]

    def greek_words(self, gv) -> list:
        """Mots graphiques grecs du prompt, normalisés selon `greek`."""
        return [norm_grc(w, self.greek) for w in gv.graphic_words(self.layer)]

    def _ask(self, prompt: str) -> str:
        # think=False : sans cela, les modèles « à réflexion » (gemma4, deepseek-r1…)
        # réfléchissent longuement avant de répondre (plusieurs minutes par verset)
        body = {"model": self.model, "stream": False, "format": SCHEMA, "think": self.think,
                "options": {"temperature": 0, "seed": self.seed},
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.load(r)
        # comptes d'Ollama, repris dans perf.json (le serveur est un autre processus :
        # son CPU n'est pas mesuré par perf.py) ; durées en nanosecondes
        for key in ("prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration"):
            self.stats[f"ollama_{key}"] += resp.get(key, 0)
        return resp["message"]["content"]

    def align(self, hv, gv) -> VerseAlignment:
        """Liens sous la méthode "llm" ; le tableau brut est gardé (llm_table)."""
        hb_tok, gr_tok = hv.tokens(self.layer), gv.tokens(self.layer)
        prompt = PROMPT.format(hb=" ".join(self.hebrew_words(hv)),
                               gr=" ".join(self.greek_words(gv)))
        for _ in range(2):  # un nouvel essai si la réponse n'est pas du JSON valide
            try:
                rows = json.loads(self._ask(prompt))["rows"]
                break
            except (json.JSONDecodeError, KeyError, TypeError):
                self.stats["reponses_invalides"] += 1
        else:
            self.stats["versets_sans_reponse"] += 1
            return VerseAlignment(hb_tok, gr_tok, {"llm": []}, {"llm_table": []})

        links = table_to_links(hb_tok, gr_tok, rows)
        self.stats["versets"] += 1
        self.stats["tokens_hb_sans_lien"] += len(hb_tok) - len({i for i, _ in links})
        self.stats["tokens_gr_sans_lien"] += len(gr_tok) - len({j for _, j in links})
        return VerseAlignment(hb_tok, gr_tok, {"llm": links}, {"llm_table": rows})
