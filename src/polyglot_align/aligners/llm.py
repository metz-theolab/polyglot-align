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

Garde-fous (DECISIONS.md « Aligneur LLM : limite de génération et réponses
tronquées ») : génération limitée à `num_predict` tokens ; une réponse coupée
par cette limite (boucle de répétition) garde ses lignes complètes ; un délai
dépassé compte le verset « sans réponse » ; un serveur injoignable arrête
l'expérience (qui se reprend ensuite).
"""
import json
import urllib.error
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


TIMEOUT = 600   # secondes par requête ; avec num_predict, une réponse prend moins d'une minute


def complete_rows(text: str) -> list:
    """Lignes complètes d'un tableau JSON {"rows": [{...}, {...}, …]} coupé
    en cours d'écriture : les objets lisibles en entier, dans l'ordre, jusqu'à
    la coupure. Compact ou indenté ; [] s'il n'y a pas de tableau."""
    i = text.find("[")
    if i < 0:
        return []
    decoder, rows = json.JSONDecoder(), []
    i += 1
    while True:
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        try:
            obj, i = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            return rows
        if not isinstance(obj, dict):
            return rows
        rows.append(obj)


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
        "num_predict": 4096,     # tokens générés au plus par verset (null = sans limite)
    }

    @classmethod
    def check_params(cls, params: dict) -> list:
        problems = [] if params["model"] else ["aligner llm : `model` n'est pas donné (ex. gemma4:12b)"]
        n = params["num_predict"]
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n <= 0):
            problems.append(f"aligner llm : num_predict = {n!r} (attendu : un entier positif, ou null)")
        return problems

    def __init__(self, model: str, url: str = "http://localhost:11434", think: bool = False,
                 seed: int = 1, num_predict: int | None = 4096, layer: str = "w",
                 hebrew: str = "pointed", greek: str = "accented"):
        super().__init__(layer, hebrew, greek)
        self.model, self.url, self.think, self.seed = model, url.rstrip("/"), think, seed
        self.num_predict = num_predict

    def hebrew_words(self, hv) -> list:
        """Mots graphiques hébreux du prompt, normalisés selon `hebrew`
        (pointed : texte tel qu'exporté)."""
        return [norm_heb(w, self.hebrew) for w in hv.graphic_words(self.layer)]

    def greek_words(self, gv) -> list:
        """Mots graphiques grecs du prompt, normalisés selon `greek`."""
        return [norm_grc(w, self.greek) for w in gv.graphic_words(self.layer)]

    def _ask(self, prompt: str) -> tuple[str, str]:
        """Envoie le prompt ; renvoie (réponse, done_reason d'Ollama : "stop",
        ou "length" si la génération a été coupée par num_predict).
        Délai dépassé : TimeoutError. Serveur injoignable ou en erreur :
        RuntimeError (arrête l'expérience)."""
        # think=False : sans cela, les modèles « à réflexion » (gemma4, deepseek-r1…)
        # réfléchissent longuement avant de répondre (plusieurs minutes par verset)
        options = {"temperature": 0, "seed": self.seed}
        if self.num_predict is not None:
            options["num_predict"] = self.num_predict
        body = {"model": self.model, "stream": False, "format": SCHEMA, "think": self.think,
                "options": options, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(f"{self.url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                resp = json.load(r)
        except urllib.error.HTTPError as e:      # le serveur répond, mais par une erreur
            raise RuntimeError(f"Ollama ({self.url}) : erreur HTTP {e.code} ({e.reason})") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise TimeoutError(f"pas de réponse d'Ollama en {TIMEOUT} s") from e
            raise RuntimeError(f"Ollama injoignable ({self.url}) : {e.reason} ; démarrer le "
                               "serveur puis relancer l'expérience (elle reprendra)") from e
        # comptes d'Ollama, repris dans perf.json (le serveur est un autre processus :
        # son CPU n'est pas mesuré par perf.py) ; durées en nanosecondes
        for key in ("prompt_eval_count", "eval_count", "prompt_eval_duration", "eval_duration"):
            self.stats[f"ollama_{key}"] += resp.get(key, 0)
        return resp["message"]["content"], resp.get("done_reason", "stop")

    def ask_table(self, prompt: str):
        """Lignes du tableau répondu par le modèle, ou None (verset sans
        réponse). Réponse coupée par num_predict : lignes complètes, sans
        nouvel essai (à température 0, il redonnerait la même boucle).
        Réponse illisible : un nouvel essai."""
        for _ in range(2):
            try:
                content, done_reason = self._ask(prompt)
            except TimeoutError:
                self.stats["delais_depasses"] += 1
                return None
            if done_reason == "length":
                self.stats["reponses_tronquees"] += 1
                return complete_rows(content)
            try:
                rows = json.loads(content)["rows"]
                if isinstance(rows, list) and all(isinstance(r, dict) for r in rows):
                    return rows
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
            self.stats["reponses_invalides"] += 1
        return None

    def align(self, hv, gv) -> VerseAlignment:
        """Liens sous la méthode "llm" ; le tableau brut est gardé (llm_table)."""
        hb_tok, gr_tok = hv.tokens(self.layer), gv.tokens(self.layer)
        prompt = PROMPT.format(hb=" ".join(self.hebrew_words(hv)),
                               gr=" ".join(self.greek_words(gv)))
        rows = self.ask_table(prompt)
        if rows is None:
            self.stats["versets_sans_reponse"] += 1
            return VerseAlignment(hb_tok, gr_tok, {"llm": []}, {"llm_table": []})

        links = table_to_links(hb_tok, gr_tok, rows)
        self.stats["versets"] += 1
        self.stats["tokens_hb_sans_lien"] += len(hb_tok) - len({i for i, _ in links})
        self.stats["tokens_gr_sans_lien"] += len(gr_tok) - len({j for _, j in links})
        return VerseAlignment(hb_tok, gr_tok, {"llm": links}, {"llm_table": rows})
