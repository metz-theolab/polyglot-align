# Alignement hébreu – grec (LXX)

Alignement mot à mot du texte hébreu et de la Septante, évalué contre un gold
standard (`data/gold/`).

## Avant de coder

Lire [DECISIONS.md](DECISIONS.md) : c'est la référence des choix d'architecture
et de traitement des données. Respecter les entrées au statut `décidé` ; pour un
point `à trancher`, demander plutôt que choisir seul.

Les décisions se prennent en discussion « brainstorming » et sont consignées
dans `DECISIONS.md`. Si une discussion de code fait apparaître une décision
nouvelle, la proposer pour ce fichier au lieu de la laisser implicite dans le
code.

`DECISIONS.md` sert aussi de base à la rédaction de l'article et des slides.
Chaque entrée doit pouvoir être reprise telle quelle dans une section
« Méthode » : énoncer la décision, la justifier (raison philologique ou
technique), donner les chiffres qui la fondent (nombre de cas, exemples avec
références bibliques) et les options écartées avec leur raison.

## Structure

Une expérience = un fichier YAML dans `experiments/` ; une seule commande :
`python src/run.py experiments/<nom>.yaml` → résultats dans `results/<name>/`
(alignements JSONL, CSV de relecture, `scores.csv`, `scores.json`, copie de la
config).

Classes (`src/`) :
- `config.py` — `Config`, `Passage` : lecture et vérification du YAML
- `corpus.py` — `Corpus`, `Verse` : textes exportés (seul lecteur des couches
  `t` / `w` / `l` / `g`)
- `aligners.py` — `Aligner` (interface), `SimAlignAligner`, `make_aligner` ;
  `llm_align.py` — `OllamaAligner` (LLM local, tableau → liens)
- `gold.py` — `Gold` : unités CATSS, rattachement des tokens aux blocs, règle
  « lien juste »
- `evaluate.py` — `Evaluator` : jugement des liens, mesures, CSV de relecture
- `experiment.py` — `Experiment` : enchaîne alignement, évaluation, total, écriture
- `align.py` — parcours des versets d'un passage et écriture du JSONL

Fonctions et scripts : `normalize.py` (normalisation des tokens),
`gold_clean.py` (gold CATSS → `data/gold_clean/<livre>.json`), `show.py`
(relire un verset : `python src/show.py results/<name>/Gen.1.jsonl Gen.1.1`),
`run.py` (ligne de commande).

Données : `data/export_bhsa_tf.py`, `data/export_lxx_tf.py` (export Text-Fabric,
à lancer depuis `data/`) → `data/he/`, `data/lxx/` (format dans `DECISIONS.md`) ;
`data/gold/` (CATSS brut).

Tests : `python -m unittest discover -s tests` ; non-régression :
`python tests/check_non_regression.py` (références dans `tests/reference/`).
