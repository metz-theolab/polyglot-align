"""Routes de l'API (préfixe /api/v1, ajouté dans main.py)."""
from fastapi import Request

from polyglot_api.services.aligner import AlignerService
from polyglot_api.settings import Settings


def get_service(request: Request) -> AlignerService:
    return request.app.state.service


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
