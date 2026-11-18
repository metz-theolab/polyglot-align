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
from polyglot_api.routes import reader as reader_routes
from polyglot_api.services.aligner import AlignerService, NotReady, UnknownAlgorithm
from polyglot_api.services.reader import Reader
from polyglot_api.settings import Settings

log = logging.getLogger(__name__)

PREFIX = "/api/v1"


LABELS = {
    "eflomal": "eflomal — statistical",
    "simalign": "SimAlign — ({model})",
    "llm": "LLM — {model} (Ollama)",
}


def label(name: str, settings: Settings) -> str:
    model = {"simalign": settings.simalign_model, "llm": settings.llm_model}.get(name, "")
    return LABELS.get(name, name).format(model=model)


def ollama_check(settings: Settings):
    """Raison d'indisponibilité du LLM (serveur Ollama injoignable, modèle
    absent), ou None s'il est prêt."""
    def check():
        import json
        import urllib.request
        try:
            with urllib.request.urlopen(f"{settings.ollama_url.rstrip('/')}/api/tags", timeout=2) as r:
                models = {m["name"] for m in json.load(r).get("models", [])}
        except Exception:
            return f"Ollama not reachable at {settings.ollama_url}"
        if settings.llm_model not in models:
            return f"model {settings.llm_model} is not installed in Ollama (ollama pull {settings.llm_model})"
        return None
    return check


def default_service(settings: Settings, store) -> AlignerService:
    """Aligneurs réels : socle (données du DataStore, segmentation table +
    dictabert-seg) puis les algorithmes de settings.algorithms, dans l'ordre."""
    def base():
        from polyglot_align.segment import CombinedSegmenter
        return {"store": store, "segmenter": CombinedSegmenter.from_store(store, device=settings.device)}

    def eflomal(b):
        from polyglot_align.textalign import TextAligner
        return TextAligner(b["store"], segmenter=b["segmenter"])

    def simalign(b):
        from polyglot_align.textalign import SimAlignTextAligner
        return SimAlignTextAligner(b["segmenter"], model=settings.simalign_model, device=settings.device)

    def llm(b):
        from polyglot_align.textalign import LLMTextAligner
        return LLMTextAligner(b["segmenter"], model=settings.llm_model, url=settings.ollama_url)

    known = {"eflomal": eflomal, "simalign": simalign, "llm": llm}
    unknown = [a for a in settings.algorithms if a not in known]
    if unknown:
        raise ValueError(f"POLYGLOT_ALGORITHMS : algorithme(s) inconnu(s) {unknown} "
                         f"(possibles : {list(known)})")
    return AlignerService(base, {a: known[a] for a in settings.algorithms},
                          checks={"llm": ollama_check(settings)})


def create_app(settings: Settings | None = None, service: AlignerService | None = None,
               reader: Reader | None = None) -> FastAPI:
    """Construit l'application. service, reader : à fournir en test (aligneur
    simulé, petits résultats). Un seul DataStore (settings.data_dir) pour les
    deux."""
    from polyglot_align.store import DataStore
    settings = settings or Settings()
    store = DataStore(settings.data_dir) if service is None or reader is None else None
    service = service or default_service(settings, store)
    reader = reader or Reader(store, settings.results_dir, settings.reader_corpora,
                              settings.reader_method, settings.reader_cache)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.load_on_startup and service.base is None and service.status == "loading":
            # en arrière-plan : l'API répond tout de suite (/health : loading)
            threading.Thread(target=service.load, name="chargement", daemon=True).start()
        yield

    app = FastAPI(title="polyglot-align API", version=__version__, lifespan=lifespan,
                  description="Alignement mot à mot d'un texte hébreu et d'un texte grec "
                              "(eflomal, appris sur la Bible hébraïque et la Septante).")
    app.state.settings, app.state.service, app.state.reader = settings, service, reader
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(NotReady)
    async def not_ready(request: Request, exc: NotReady):
        return JSONResponse({"detail": str(exc)}, status_code=503, headers={"Retry-After": "10"})

    @app.exception_handler(UnknownAlgorithm)
    async def unknown_algorithm(request: Request, exc: UnknownAlgorithm):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    app.include_router(health.router, prefix=PREFIX)
    app.include_router(align.router, prefix=PREFIX)
    app.include_router(reader_routes.router, prefix=PREFIX)
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
