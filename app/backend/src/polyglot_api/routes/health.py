"""État de l'API (contrôle de santé du conteneur) et description de ses réglages."""
from fastapi import APIRouter, Depends, Response

from polyglot_api import __version__
from polyglot_api.routes import get_service, get_settings
from polyglot_api.schemas import Health, Info
from polyglot_api.services.aligner import AlignerService
from polyglot_api.settings import Settings

router = APIRouter(tags=["état"])

LIMITS = [
    "Hebrew ↔ Greek only (eflomal was trained on these two languages)",
    "results vary slightly from one call to the next (eflomal is not deterministic)",
    "consonantal segmentation: possible ambiguities (interrogative ה, מאת…), "
    "about 0.3 % of words on biblical text",
    "a text is handled as one block, even if it spans several verses",
]


def version() -> str:
    from polyglot_align import __version__ as library
    return f"polyglot-align {library}, polyglot-api {__version__}"


@router.get("/health", response_model=Health, responses={503: {"model": Health}})
def health(response: Response, service: AlignerService = Depends(get_service)) -> Health:
    """`ready` (200) quand les modèles sont chargés ; `loading` ou `error` (503) sinon."""
    if service.status != "ready":
        response.status_code = 503
    return Health(status=service.status, detail=service.detail, loading_s=service.loading_s)


@router.get("/info", response_model=Info)
def info(service: AlignerService = Depends(get_service),
         settings: Settings = Depends(get_settings)) -> Info:
    """Méthode, réglages, limites (à afficher dans le front)."""
    aligner = service.aligner
    return Info(version=version(), tokens="w",
                hebrew=getattr(aligner, "hebrew", "unvocalized"),
                greek=getattr(aligner, "greek", "unaccented"),
                segmenter=getattr(getattr(aligner, "segmenter", None), "name", None) or "table+dictabert-seg",
                max_chars=settings.max_chars, max_batch=settings.max_batch, limits=LIMITS)
