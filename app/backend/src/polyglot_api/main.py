"""Application FastAPI de l'API REST (decisions-app.md, « Architecture du backend »).

Lancer (depuis la racine du dépôt, venv activé) :
    polyglot-api                                   # réglages : variables POLYGLOT_…
    POLYGLOT_PORT=8080 polyglot-api
ou avec uvicorn directement :
    uvicorn polyglot_api.main:create_app --factory --host 0.0.0.0 --port 8000

Documentation interactive : http://<hôte>:<port>/docs
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from polyglot_api import __version__
from polyglot_api.routes import align, health
from polyglot_api.services.aligner import AlignerService, NotReady
from polyglot_api.settings import Settings

log = logging.getLogger(__name__)

PREFIX = "/api/v1"


def default_factory(settings: Settings):
    """TextAligner réel : données de settings.data_dir, segmentation table +
    dictabert-seg sur settings.device."""
    def factory():
        from polyglot_align.segment import CombinedSegmenter
        from polyglot_align.store import DataStore
        from polyglot_align.textalign import TextAligner
        store = DataStore(settings.data_dir)
        return TextAligner(store, segmenter=CombinedSegmenter.from_store(store, device=settings.device))
    return factory


def create_app(settings: Settings | None = None, service: AlignerService | None = None) -> FastAPI:
    """Construit l'application. service : à fournir en test (aligneur simulé)."""
    settings = settings or Settings()
    service = service or AlignerService(default_factory(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.load_on_startup and service.status == "loading":
            # en arrière-plan : l'API répond tout de suite (/health : loading)
            threading.Thread(target=service.load, name="chargement", daemon=True).start()
        yield

    app = FastAPI(title="polyglot-align API", version=__version__, lifespan=lifespan,
                  description="Alignement mot à mot d'un texte hébreu et d'un texte grec "
                              "(eflomal, appris sur la Bible hébraïque et la Septante).")
    app.state.settings, app.state.service = settings, service
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(NotReady)
    async def not_ready(request: Request, exc: NotReady):
        return JSONResponse({"detail": str(exc)}, status_code=503, headers={"Retry-After": "10"})

    app.include_router(health.router, prefix=PREFIX)
    app.include_router(align.router, prefix=PREFIX)
    return app


def main() -> None:
    """Commande polyglot-api : lance le serveur avec les réglages POLYGLOT_…"""
    import uvicorn
    from polyglot_align.cli import setup_logging
    setup_logging()                       # journal de polyglot_align (apprentissage d'eflomal…)
    logging.getLogger("polyglot_api").setLevel(logging.INFO)
    logging.getLogger("polyglot_api").addHandler(logging.getLogger("polyglot_align").handlers[0])
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
