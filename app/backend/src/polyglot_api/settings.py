"""Réglages de l'API, lus dans les variables d'environnement (préfixe POLYGLOT_).

Aucune adresse ni aucun chemin n'est écrit en dur : la même image Docker
servira en local et sur un serveur (decisions-app.md).

    POLYGLOT_DATA_DIR       dossier data/ de polyglot-align (corpus, table des versets)
    POLYGLOT_HOST           adresse d'écoute (0.0.0.0 dans un conteneur)
    POLYGLOT_PORT           port
    POLYGLOT_CORS_ORIGINS   origines autorisées, liste JSON : '["http://localhost:5173"]'
    POLYGLOT_DEVICE         cpu, mps, cuda (dictabert-seg)
    POLYGLOT_MAX_CHARS      longueur maximale d'un texte (caractères)
    POLYGLOT_MAX_BATCH      nombre maximal de paires par requête /align/batch
    POLYGLOT_LOAD_ON_STARTUP  charger les modèles au démarrage (false : tests)
    POLYGLOT_ALGORITHMS     algorithmes proposés, liste JSON : '["eflomal", "simalign", "llm"]'
                            (le premier est celui par défaut)
    POLYGLOT_SIMALIGN_MODEL modèle de SimAlign (Hugging Face)
    POLYGLOT_OLLAMA_URL     serveur Ollama du LLM
    POLYGLOT_LLM_MODEL      modèle Ollama du LLM
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYGLOT_")

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]   # serveur de développement Vite
    device: str = "cpu"
    max_chars: int = 5000
    max_batch: int = 20
    load_on_startup: bool = True
    algorithms: list[str] = ["eflomal", "simalign", "llm"]
    simalign_model: str = "cis-lmu/glot500-base"
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "gemma4:12b"
