# polyglot-api : API REST de l'app de test

Aligne un texte hébreu et un texte grec saisis, avec trois algorithmes au
choix : eflomal (appris sur la Bible hébraïque et la Septante plus le texte
saisi), SimAlign (Glot500) et un LLM servi par Ollama (Gemma 4 12B). Couche
mince au-dessus de la bibliothèque `polyglot_align` (`textalign.py`).

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
| `POLYGLOT_ALGORITHMS` | `["eflomal", "simalign", "llm"]` | algorithmes proposés (le premier par défaut) |
| `POLYGLOT_SIMALIGN_MODEL` | `cis-lmu/glot500-base` | modèle de SimAlign |
| `POLYGLOT_OLLAMA_URL` | `http://localhost:11434` | serveur Ollama du LLM |
| `POLYGLOT_LLM_MODEL` | `gemma4:12b` | modèle Ollama |
| `POLYGLOT_RESULTS_DIR` | `results` | dossier `results/` de polyglot-align (lecteur) |
| `POLYGLOT_READER_CORPORA` | `["eflomal_unvocalized", "eflomal_syr"]` | résultats publiés dans le lecteur |
| `POLYGLOT_READER_METHOD` | `gdfa` | liens affichés par le lecteur |
| `POLYGLOT_READER_CACHE` | `16` | livres gardés en mémoire par le lecteur |

Le LLM n'est proposé que si Ollama répond et connaît le modèle ; sinon il
apparaît « unavailable » dans `/info`, avec la raison, et est revérifié à
chaque appel de `/info` (Ollama démarré après l'API).

## Routes (`/api/v1`)

| Route | Rôle |
|---|---|
| `GET /health` | `ready` (200), `loading` ou `error` (503) |
| `GET /info` | algorithmes et leur état (`ready`, `loading`, `unavailable`), réglages, limites |
| `POST /align` | `{"hebrew": "…", "greek": "…", "algorithm": "eflomal"}` → tokens, mots graphiques, liens `sure` et `all` |
| `POST /align/batch` | `{"pairs": [{…}, …]}` : plusieurs paires, un seul apprentissage |
| `POST /segment` | `{"hebrew": "…"}` → découpage en mots BHSA, sans aligner |
| `GET /reader/corpora` | résultats publiés : cible (lxx, syr), langue, sens d'écriture, gold |
| `GET /reader/books` | livres hébreux alignés, chapitres, textes cibles (Judg et JudgA…) |
| `GET /reader/{livre}/{chapitre}` | chapitre hébreu en pivot ; `?corpus=…` (répétable) : résultats à inclure |

Lecteur (`/reader`) : alignements déjà calculés (`results/<nom>/*.jsonl`),
l'hébreu en pivot. Chaque verset : `words` (mots hébreux séparés par des
espaces ; `graphic: false` pour ס, פ, ׀) et `targets`, un par texte cible
(`tokens` du corpus, `links` : couples `[mot pivot, token cible]`, `verdicts` :
verdict du gold par mot pivot, LXX seulement). Verset sans équivalent : pas de
cible. Dossier de résultats absent : non publié (avertissement au démarrage).

Réponse de `/align` : `hebrew` et `greek` (`text`, `tokens`, `graphic` : numéro
du mot graphique de chaque token), `links` (`sure` : liens sûrs ; `all` : sûrs
+ probables ; couples `[i, j]` d'indices de tokens), `algorithm`, `methods`
(à quoi correspondent `sure` et `all` : eflomal inter / gdfa, SimAlign argmax
/ itermax, LLM un seul niveau), `notes` (ex. réponse du LLM tronquée),
`unknown_hebrew_words` (mots absents de BHSA, découpés par dictabert-seg),
`meta` (réglages, durée, versions). Erreurs : 422 texte sans hébreu ou sans
grec, algorithme inconnu ; 413 texte trop long ; 503 modèles pas encore
chargés ou algorithme indisponible.

## Tests

```bash
python -m unittest discover -s app/backend/tests   # aligneur simulé, sans modèle
```
