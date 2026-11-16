# Décisions de l'app de test (API et front)

Journal des décisions de l'app : backend (API REST) et frontend. L'app est un
projet distinct de la recherche ; ses décisions ne vont pas dans
`DECISIONS.md` (méthode et résultats de l'article). Le cœur de l'app
(segmentation de l'hébreu saisi, `align("texte A", "texte B")`) est décrit
dans `DECISIONS.md`, entrées du 2026-11-16 « Segmentation de l'hébreu saisi,
pour l'app de test » et « `align("texte A", "texte B")` ».

Chaque entrée : date, décision, raison, statut (`proposé` / `décidé` / `fait`).

---

## 2026-11-16 — Architecture du backend : API REST mince, paquet indépendant

**Statut : fait** (2026-11-16, branche `feat/api-backend`). Paquet
`app/backend` (`polyglot_api`, commande `polyglot-api`), FastAPI 0.163,
uvicorn 0.54, pydantic-settings 2.16 ; 16 tests (`app/backend/tests`,
aligneur simulé) ; mode d'emploi dans `app/backend/README.md`. Essai avec le
vrai serveur : `/health` répond dès 1,3 s (`loading`, 503), modèles chargés
en 3,7 s (`ready`) ; `/align` sur Gn 1:3 en 6,6 s (וַ ↔ καὶ, יֹּאמֶר ↔ εἶπεν,
אֱלֹהִים ↔ θεός, יְהִי ↔ Γενηθήτω, אוֹר ↔ φῶς, יְהִי ↔ ἐγένετο) ; texte sans
hébreu : 422 avec message ; `/docs` servi. Ajouts par rapport à la
conception : chargement en arrière-plan (l'API répond pendant le
chargement), état `error` si le chargement échoue (message dans `/health`),
route `/segment`, `unknown_hebrew_words` dans la réponse (mots absents de
BHSA, découpés par dictabert-seg).

**Prévu pour Docker** (décidé le 2026-11-16 : `docker-compose up` lancera le
back et le front, plus tard) : tous les réglages par variables
d'environnement (`POLYGLOT_HOST=0.0.0.0` dans le conteneur, `POLYGLOT_DATA_DIR`,
`POLYGLOT_CORS_ORIGINS`…), `/api/v1/health` pour le contrôle de santé du
conteneur (503 tant que les modèles ne sont pas chargés), aucune adresse
écrite en dur. Points à régler au moment de Docker : l'image doit contenir
`data/` (ou le monter), compiler eflomal (OpenMP) et embarquer torch pour
dictabert-seg (image lourde) ; le cache Hugging Face (`HF_HOME`) doit être
un volume pour ne pas retélécharger dictabert-seg (740 Mo) à chaque
démarrage.

**Décision.** Le backend est un paquet Python indépendant, `polyglot_api`
(`app/backend/`), qui dépend de `polyglot-align` et l'importe comme une
bibliothèque. Toute la logique (segmentation, eflomal, `TextAligner`) reste
dans `polyglot_align` ; le backend ne fait que traduire HTTP ↔ `TextAligner`.

**Raison.** La bibliothèque reste sans dépendance web (les expériences de
l'article n'installent pas FastAPI) ; l'API ne duplique aucune règle ; ce
qui est testé dans la bibliothèque vaut pour l'API ; le backend peut être
déployé seul.

**Structure :**

```
app/
  backend/
    pyproject.toml              polyglot_api : fastapi, uvicorn, pydantic-settings ;
                                dépend de polyglot-align (même venv, mode éditable)
    src/polyglot_api/
      main.py                   create_app() : FastAPI, CORS, routes ; TextAligner
                                chargé une fois au démarrage
      settings.py               réglages par variables d'environnement
      schemas.py                modèles pydantic des requêtes et réponses
      services/aligner.py       AlignerService : garde le TextAligner, un
                                alignement à la fois (verrou)
      routes/
        align.py                POST /api/v1/align, POST /api/v1/align/batch
        segment.py              POST /api/v1/segment
        health.py               GET /api/v1/health, GET /api/v1/info
    tests/
      test_api.py               client de test FastAPI, aligneur simulé
  frontend/                     plus tard
```

Installation : `pip install -e .` (bibliothèque), puis
`pip install -e app/backend` (API), dans le même venv.

**Choix :**
- *Chargement unique au démarrage* (environ 10 s : dictabert-seg, table de
  segmentation, données) ; `/health` dit si l'API est prête, `/align`
  répond 503 tant qu'elle ne l'est pas. Écarté : charger à chaque requête
  (défaut de l'app d'alma : `Collation(...)` dans la route).
- *Un alignement à la fois* : eflomal occupe tous les cœurs environ 7 s ;
  les requêtes attendent leur tour (verrou). `/align/batch` aligne plusieurs
  paires avec un seul apprentissage.
- *Réponses synchrones* pour l'app de test (environ 7 s par requête). Si
  l'app devient publique : tâches (identifiant renvoyé, résultat demandé
  ensuite).
- *Réponse* : `TextAlignment.to_dict()` (hébreu et grec : texte, tokens,
  numéros de mots graphiques ; liens `inter` et `gdfa`) et un bloc `meta`
  (réglages, durée, version, nombre de mots segmentés par dictabert-seg).
- *Erreurs* : 422 texte sans hébreu ou sans grec ; 413 texte trop long ;
  503 modèles pas encore chargés.
- *API versionnée* (`/api/v1/…`), documentation interactive automatique
  (`/docs`).
- *Réglages par variables d'environnement* : dossier `data/`
  (`POLYGLOT_DATA_DIR`), origines autorisées (jamais `*`), device, longueur
  maximale des textes. Aucune adresse écrite en dur (défaut de l'app d'alma).
- *Front, plus tard* : en développement, le serveur Vite renvoie `/api` vers
  FastAPI ; en production, FastAPI sert le front compilé (un seul processus).

**Écarté :** le backend comme module de `polyglot_align` avec un extra
`[api]` (la bibliothèque porterait le code web).
