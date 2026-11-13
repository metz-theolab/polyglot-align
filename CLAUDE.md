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

- `config.yaml` : configuration d'une expérience (passages, couche, accents,
  modèle) ; une seule commande : `python src/run.py config.yaml`
- `src/run.py` : aligne puis évalue ; résultats dans `results/<name>/`
  (alignements JSONL, `scores.csv`, `scores.json`, copie de la config)
- `src/align.py`, `src/evaluate.py`, `src/normalize.py` : bibliothèques
- `src/show.py` : relire un verset aligné
  (`python src/show.py results/<name>/Gen.1.jsonl Gen.1.1`)
- `src/gold_clean.py` : gold CATSS → `data/gold_clean/<livre>.json`
- `data/export_bhsa_tf.py`, `data/export_lxx_tf.py` : export des textes depuis
  Text-Fabric (à lancer depuis `data/`)
- `data/he/`, `data/lxx/` : textes par livre, couches `t` / `w` / `l` / `g`
  (format décrit dans `DECISIONS.md`)
- `data/gold/` : gold standard brut CATSS (avec balisage)
- `tests/` : `python -m unittest discover -s tests`
