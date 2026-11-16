"""Modèles des requêtes et réponses de l'API (contrat avec le front).

Les liens sont des couples [i, j] : i = indice d'un token hébreu, j = indice
d'un token grec (listes `tokens`). `graphic[i]` = numéro du mot graphique du
token i (בְּ et רֵאשִׁית : même mot graphique בְּרֵאשִׁית). Deux niveaux pour
tous les algorithmes : `sure` (liens sûrs) est toujours inclus dans `all`
(sûrs + probables) ; `methods` dit à quoi ils correspondent (eflomal :
inter / gdfa ; SimAlign : argmax / itermax ; LLM : un seul niveau).
Voir decisions-app.md.
"""
from typing import Literal

from pydantic import BaseModel, Field


class AlignRequest(BaseModel):
    hebrew: str = Field(description="texte hébreu, vocalisé ou non", examples=["בְּרֵאשִׁית בָּרָא אֱלֹהִים"])
    greek: str = Field(description="texte grec", examples=["ἐν ἀρχῇ ἐποίησεν ὁ θεός"])
    algorithm: str | None = Field(None, description="eflomal, simalign, llm (défaut : le premier proposé)")


class Pair(BaseModel):
    hebrew: str
    greek: str


class BatchRequest(BaseModel):
    pairs: list[Pair] = Field(min_length=1, description="paires alignées ensemble (eflomal : un seul "
                                                        "apprentissage)")
    algorithm: str | None = None


class SegmentRequest(BaseModel):
    hebrew: str = Field(examples=["בְּרֵאשִׁית בָּרָא אֱלֹהִים"])


class Side(BaseModel):
    """Un texte saisi, découpé comme le corpus."""
    text: str
    tokens: list[str] = Field(description="tokens (mots BHSA côté hébreu, mots côté grec)")
    graphic: list[int] = Field(description="numéro du mot graphique de chaque token")


class Links(BaseModel):
    sure: list[tuple[int, int]] = Field(description="liens sûrs")
    all: list[tuple[int, int]] = Field(description="liens sûrs et probables (sure inclus)")


class Methods(BaseModel):
    sure: str = Field(description="méthode des liens sûrs (ex. inter)")
    all: str = Field(description="méthode des liens sûrs et probables (ex. gdfa)")


class Alignment(BaseModel):
    hebrew: Side
    greek: Side
    links: Links
    algorithm: str
    methods: Methods
    notes: list[str] = Field(default_factory=list, description="remarques (ex. réponse du LLM tronquée)")
    unknown_hebrew_words: list[str] = Field(
        description="mots graphiques hébreux absents de BHSA, découpés par dictabert-seg")


class Meta(BaseModel):
    algorithm: str
    tokens: str = Field(description="couche de tokens (w = mots BHSA)")
    hebrew: str = Field(description="normalisation de l'hébreu donnée à l'aligneur")
    greek: str = Field(description="normalisation du grec donnée à l'aligneur")
    duration_s: float = Field(description="durée de l'alignement (apprentissage compris)")
    version: str = Field(description="versions de polyglot-align et de polyglot-api")


class AlignResponse(Alignment):
    meta: Meta


class BatchResponse(BaseModel):
    results: list[Alignment]
    meta: Meta


class SegmentResponse(BaseModel):
    hebrew: Side
    unknown_hebrew_words: list[str]


class Health(BaseModel):
    status: Literal["loading", "ready", "error"]
    detail: str | None = None
    loading_s: float | None = Field(None, description="durée du chargement des modèles")


class Algorithm(BaseModel):
    name: str
    label: str
    status: Literal["loading", "ready", "unavailable"]
    detail: str | None = Field(None, description="raison si indisponible")


class Info(BaseModel):
    version: str
    algorithms: list[Algorithm] = Field(description="dans l'ordre ; le premier est celui par défaut")
    default: str
    tokens: str = "w"
    segmenter: str
    max_chars: int
    max_batch: int
    limits: list[str]
