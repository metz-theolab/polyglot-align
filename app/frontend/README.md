# Front de l'app de test (React + Vite)

Saisie d'un texte hébreu (A) et d'un texte grec (B), choix de l'algorithme
(eflomal, SimAlign, LLM : liste et état fournis par l'API), menu d'exemples
(`src/examples.js`), alignement affiché en interlinéaire : une case par mot graphique hébreu (de
droite à gauche) avec les mots grecs reliés, puis le texte grec dans son
ordre. Une couleur par mot hébreu, reprise sur ses correspondants ; survoler
un mot surligne ses correspondants. Liens sûrs en trait plein, liens
probables en pointillé (le LLM n'a qu'un niveau).

Mode **Read** (barre d'application) : alignements déjà calculés
(`results/`), un chapitre à la fois, l'hébreu en pivot. Sous chaque mot
hébreu, ses correspondants grecs (LXX) et syriaques (Peshitta) ; boutons
**Greek** / **Syriac** : vue trilingue ou bilingue ; **Gold** : verdict du
gold CATSS (LXX). Survoler un mot grec allume le mot hébreu et ses
correspondants syriaques. Adresse partageable : `#/read/Gen/1/3`.

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
| `src/api.js` | appels à l'API (`/api/v1/health`, `/info`, `/align`, `/reader/…`) |
| `src/alignment.js` | calculs de la vue : mots graphiques, couleurs, liens, survol (testés) |
| `src/reader.js` | calculs du lecteur : mots pivots, liens par cible, survol, références, routes (testés) |
| `src/App.jsx` | barre d'application (logo, modes Align `#/align` et Read `#/read/Gen/1/3`, lien GitHub), pied de page |
| `src/assets/logo-dark.png` | logo clair sur fond transparent, pour la barre foncée (provisoire) |
| `src/components/AlignPage.jsx` | mode Align : état de l'API, saisie, résultat |
| `src/components/ReaderPage.jsx` | mode Read : navigation, boutons Greek / Syriac / Gold, chapitre |
| `src/components/VerseView.jsx` | un verset : interlinéaire hébreu pivot, textes cibles, survol |
| `src/components/AlignForm.jsx` | saisie des textes et choix de l'algorithme |
| `src/components/Alignment.jsx` | vue interlinéaire et texte grec, survol |
| `src/styles.css` | thème clair et sombre, teintes des liens |
