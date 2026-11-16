"""Modèles des requêtes et réponses de l'API (contrat avec le front).

Les liens sont des couples [i, j] : i = indice d'un token hébreu, j = indice
d'un token grec (listes `tokens`). `graphic[i]` = numéro du mot graphique du
token i (בְּ et רֵאשִׁית : même mot graphique בְּרֵאשִׁית). `inter` est
toujours inclus dans `gdfa` (decisions-app.md, DECISIONS.md).
"""
from typing import Literal

from pydantic import BaseModel, Field


class AlignRequest(BaseModel):
    hebrew: str = Field(description="texte hébreu, vocalisé ou non", examples=["בְּרֵאשִׁית בָּרָא אֱלֹהִים"])
    greek: str = Field(description="texte grec", examples=["ἐν ἀρχῇ ἐποίησεν ὁ θεός"])


class BatchRequest(BaseModel):
    pairs: list[AlignRequest] = Field(min_length=1, description="paires alignées avec un seul apprentissage")


class SegmentRequest(BaseModel):
    hebrew: str = Field(examples=["בְּרֵאשִׁית בָּרָא אֱלֹהִים"])


class Side(BaseModel):
    """Un texte saisi, découpé comme le corpus."""
    text: str
    tokens: list[str] = Field(description="tokens (mots BHSA côté hébreu, mots côté grec)")
    graphic: list[int] = Field(description="numéro du mot graphique de chaque token")


class Links(BaseModel):
    inter: list[tuple[int, int]] = Field(description="liens sûrs : communs aux deux sens d'eflomal")
    gdfa: list[tuple[int, int]] = Field(description="inter + liens d'un seul sens (grow-diag-final-and)")


class Alignment(BaseModel):
    hebrew: Side
    greek: Side
    links: Links
    unknown_hebrew_words: list[str] = Field(
        description="mots graphiques hébreux absents de BHSA, découpés par dictabert-seg")


class Meta(BaseModel):
    aligner: Literal["eflomal"] = "eflomal"
    tokens: str = Field(description="couche de tokens (w = mots BHSA)")
    hebrew: str = Field(description="normalisation de l'hébreu donnée à eflomal")
    greek: str = Field(description="normalisation du grec donnée à eflomal")
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


class Info(BaseModel):
    version: str
    aligner: str = "eflomal"
    tokens: str
    hebrew: str
    greek: str
    segmenter: str
    max_chars: int
    max_batch: int
    limits: list[str]
