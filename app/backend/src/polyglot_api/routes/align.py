"""Alignement et segmentation de textes saisis."""
from fastapi import APIRouter, Depends, HTTPException

from polyglot_align.segment import consonantal_words, greek_verse
from polyglot_api.routes import get_service, get_settings
from polyglot_api.routes.health import version
from polyglot_api.schemas import (AlignRequest, AlignResponse, Alignment, BatchRequest,
                                  BatchResponse, Meta, SegmentRequest, SegmentResponse, Side)
from polyglot_api.services.aligner import AlignerService
from polyglot_api.settings import Settings

router = APIRouter(tags=["alignement"])


def side(verse) -> Side:
    return Side(text=verse.layers["t"], tokens=verse.tokens("w"),
                graphic=[int(k) for k in verse.graphic_numbers()])


def check_length(settings: Settings, *texts: str) -> None:
    for t in texts:
        if len(t) > settings.max_chars:
            raise HTTPException(413, f"text too long: {len(t)} characters (max {settings.max_chars})")


def check_words(pairs: list) -> None:
    """Texte sans mot hébreu ou sans mot grec -> 422, message en anglais
    (l'interface est en anglais ; la bibliothèque écrit ses messages en français)."""
    for k, (he, gr) in enumerate(pairs, 1):
        where = f"pair {k}: " if len(pairs) > 1 else ""
        if not consonantal_words(he):
            raise HTTPException(422, f"{where}no Hebrew word in text A")
        if not greek_verse(gr).layers["w"]:
            raise HTTPException(422, f"{where}no Greek word in text B")


def run(service: AlignerService, pairs: list, algorithm: str | None) -> tuple[list, Meta]:
    """Aligne et décrit l'alignement ; texte vide -> 422."""
    check_words(pairs)
    try:
        results, duration, aligner = service.align_many(pairs, algorithm)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    meta = Meta(algorithm=aligner.name, tokens="w", hebrew=aligner.hebrew, greek=aligner.greek,
                duration_s=duration, version=version())
    alignments = [Alignment(hebrew=side(r.hebrew), greek=side(r.greek),
                            links={"sure": r.links["sure"], "all": r.links["all"]},
                            algorithm=r.algorithm, methods=r.methods, notes=r.notes,
                            unknown_hebrew_words=service.unknown_words(he))
                  for r, (he, _) in zip(results, pairs)]
    return alignments, meta


@router.post("/align", response_model=AlignResponse)
def align(req: AlignRequest, service: AlignerService = Depends(get_service),
          settings: Settings = Depends(get_settings)) -> AlignResponse:
    """Aligne un texte hébreu et un texte grec avec l'algorithme demandé
    (eflomal : appris sur la table des versets plus cette paire, environ 7 s)."""
    check_length(settings, req.hebrew, req.greek)
    (alignment,), meta = run(service, [(req.hebrew, req.greek)], req.algorithm)
    return AlignResponse(**alignment.model_dump(), meta=meta)


@router.post("/align/batch", response_model=BatchResponse)
def align_batch(req: BatchRequest, service: AlignerService = Depends(get_service),
                settings: Settings = Depends(get_settings)) -> BatchResponse:
    """Aligne plusieurs paires ensemble (eflomal : un seul apprentissage)."""
    if len(req.pairs) > settings.max_batch:
        raise HTTPException(413, f"too many pairs: {len(req.pairs)} (max {settings.max_batch})")
    check_length(settings, *(t for p in req.pairs for t in (p.hebrew, p.greek)))
    alignments, meta = run(service, [(p.hebrew, p.greek) for p in req.pairs], req.algorithm)
    return BatchResponse(results=alignments, meta=meta)


@router.post("/segment", response_model=SegmentResponse)
def segment(req: SegmentRequest, service: AlignerService = Depends(get_service),
            settings: Settings = Depends(get_settings)) -> SegmentResponse:
    """Découpe un texte hébreu comme le corpus (mots BHSA), sans aligner."""
    check_length(settings, req.hebrew)
    verse = service.segment(req.hebrew)
    if not verse.layers["w"]:
        raise HTTPException(422, "no Hebrew word in the text")
    return SegmentResponse(hebrew=side(verse), unknown_hebrew_words=service.unknown_words(req.hebrew))
