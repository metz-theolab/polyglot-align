# Front de l'app de test (React + Vite)

Saisie d'un texte hébreu (A) et d'un texte grec (B), choix de l'algorithme
(eflomal, SimAlign, LLM : liste et état fournis par l'API), menu d'exemples
(`src/examples.js`), alignement affiché en interlinéaire : une case par mot graphique hébreu (de
droite à gauche) avec les mots grecs reliés, puis le texte grec dans son
ordre. Une couleur par mot hébreu, reprise sur ses correspondants ; survoler
un mot surligne ses correspondants. Liens sûrs en trait plein, liens
probables en pointillé (le LLM n'a qu'un niveau). Décisions : [decisions-app.md](../../decisions-app.md).

## Lancer en développement

Le backend doit tourner (voir [app/backend](../backend/README.md)) :

```bash
polyglot-api                       # dans le venv, depuis la racine du dépôt
```

Puis, dans `app/frontend` :

```bash
npm install
npm run dev                        # http://localhost:5173
```

Le serveur Vite renvoie les appels `/api` au backend : `VITE_API_TARGET`
(défaut `http://127.0.0.1:8000`). Aucune adresse n'est écrite dans le code.

## Autres commandes

```bash
npm test                           # tests des calculs de la vue (Vitest)
npm run build                      # version de production dans dist/
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/api.js` | appels à l'API (`/api/v1/health`, `/info`, `/align`) |
| `src/alignment.js` | calculs de la vue : mots graphiques, couleurs, liens, survol (testés) |
| `src/App.jsx` | page : état de l'API, saisie, résultat, limites |
| `src/components/AlignForm.jsx` | saisie des textes et choix de l'algorithme |
| `src/components/Alignment.jsx` | vue interlinéaire et texte grec, survol |
| `src/styles.css` | thème clair et sombre, teintes des liens |
