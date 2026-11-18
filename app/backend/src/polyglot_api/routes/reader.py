"""Lecture des alignements déjà calculés, l'hébreu en pivot (decisions-app.md,
« Lecteur des textes alignés »)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from polyglot_api.schemas import ReaderBook, ReaderChapter, ReaderCorpus, ReaderText
from polyglot_api.services.reader import Reader, UnknownPassage

router = APIRouter(prefix="/reader", tags=["lecteur"])


def get_reader(request: Request) -> Reader:
    return request.app.state.reader


@router.get("/corpora", response_model=list[ReaderCorpus])
def corpora(reader: Reader = Depends(get_reader)) -> list[ReaderCorpus]:
    """Résultats publiés (cible, langue, sens d'écriture, gold disponible)."""
    return [ReaderCorpus(id=c.name, label=c.label, target=c.target, language=c.language,
                         direction=c.direction, gold=c.gold, method=reader.method)
            for c in reader.corpora.values()]


@router.get("/books", response_model=list[ReaderBook])
def books(reader: Reader = Depends(get_reader)) -> list[ReaderBook]:
    """Livres hébreux alignés, dans l'ordre biblique, avec leurs chapitres et
    leurs textes cibles."""
    return [ReaderBook(book=b, chapters=ch, texts=[ReaderText(corpus=t.corpus, text=t.name) for t in ts])
            for b, ch, ts in reader.books()]


@router.get("/{book}/{chapter}", response_model=ReaderChapter)
def chapter(book: str, chapter: str, reader: Reader = Depends(get_reader),
            corpus: list[str] | None = Query(None, description="résultats à inclure (défaut : tous)")
            ) -> ReaderChapter:
    """Un chapitre hébreu : mots pivots de chaque verset et, par texte cible,
    tokens et liens mot pivot ↔ token."""
    unknown = set(corpus or []) - set(reader.corpora)
    if unknown:
        raise HTTPException(422, f"unknown corpus: {', '.join(sorted(unknown))}")
    try:
        verses = reader.chapter(book, chapter, corpus)
    except UnknownPassage as e:
        raise HTTPException(404, str(e)) from e
    return ReaderChapter(book=book, chapter=chapter, verses=verses)
