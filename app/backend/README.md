# polyglot-api : API REST de l'app de test

Aligne un texte hébreu et un texte grec saisis, avec eflomal appris sur la
Bible hébraïque et la Septante. Couche mince au-dessus de la bibliothèque
`polyglot_align` (`TextAligner`). Décisions : [decisions-app.md](../../decisions-app.md).

## Installation

Depuis la racine du dépôt, dans le venv :

```bash
pip install -e '.[simalign,eflomal]'   # bibliothèque (torch pour dictabert-seg, eflomal)
pip install -e 'app/backend[dev]'      # API (+ httpx pour les tests)
```

## Lancer

```bash
polyglot-api                            # http://127.0.0.1:8000, documentation : /docs
POLYGLOT_HOST=0.0.0.0 POLYGLOT_PORT=8080 polyglot-api
```

Les modèles se chargent en arrière-plan (quelques secondes) : `/api/v1/health`
répond `loading` (503) puis `ready` (200).

| Variable | Défaut | Rôle |
|---|---|---|
| `POLYGLOT_DATA_DIR` | `data` | dossier `data/` de polyglot-align |
| `POLYGLOT_HOST` | `127.0.0.1` | adresse d'écoute (`0.0.0.0` dans un conteneur) |
| `POLYGLOT_PORT` | `8000` | port |
| `POLYGLOT_CORS_ORIGINS` | `["http://localhost:5173"]` | origines autorisées (liste JSON) |
| `POLYGLOT_DEVICE` | `cpu` | `cpu`, `mps`, `cuda` (dictabert-seg) |
| `POLYGLOT_MAX_CHARS` | `5000` | longueur maximale d'un texte |
| `POLYGLOT_MAX_BATCH` | `20` | paires au plus par `/align/batch` |

## Routes (`/api/v1`)

| Route | Rôle |
|---|---|
| `GET /health` | `ready` (200), `loading` ou `error` (503) |
| `GET /info` | méthode, réglages, limites à afficher |
| `POST /align` | `{"hebrew": "…", "greek": "…"}` → tokens, mots graphiques, liens `inter` et `gdfa` |
| `POST /align/batch` | `{"pairs": [{…}, …]}` : plusieurs paires, un seul apprentissage |
| `POST /segment` | `{"hebrew": "…"}` → découpage en mots BHSA, sans aligner |

Réponse de `/align` : `hebrew` et `greek` (`text`, `tokens`, `graphic` : numéro
du mot graphique de chaque token), `links` (`inter` : liens sûrs ; `gdfa` :
inter + liens probables ; couples `[i, j]` d'indices de tokens),
`unknown_hebrew_words` (mots absents de BHSA, découpés par dictabert-seg),
`meta` (réglages, durée, versions). Erreurs : 422 texte sans hébreu ou sans
grec, 413 texte trop long, 503 modèles pas encore chargés.

## Tests

```bash
python -m unittest discover -s app/backend/tests   # aligneur simulé, sans modèle
```
