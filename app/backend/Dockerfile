# Image du backend (API REST) : bibliothèque polyglot-align + polyglot-api.
# Construite depuis la racine du dépôt (contexte : docker-compose.yml).
# Voir decisions-app.md, « Docker ».
FROM python:3.13-slim

# gcc et OpenMP pour compiler eflomal
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface

WORKDIR /srv

# torch en version CPU (sans CUDA : image bien plus légère), avant simalign
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# bibliothèque (SimAlign, eflomal), puis l'API
COPY pyproject.toml ./
COPY src ./src
RUN pip install '.[simalign,eflomal]'
COPY app/backend ./app/backend
RUN pip install ./app/backend

# données nécessaires à l'app : textes hébreu et grec, table des versets
COPY data/he ./data/he
COPY data/lxx ./data/lxx
COPY data/verse_map.json ./data/verse_map.json

ENV POLYGLOT_DATA_DIR=/srv/data \
    POLYGLOT_HOST=0.0.0.0 \
    POLYGLOT_PORT=8000
EXPOSE 8000
CMD ["polyglot-api"]
