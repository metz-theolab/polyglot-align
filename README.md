# polyglot-align

Alignement automatique mot à mot de la Bible hébraïque et de la Septante,
évalué contre l'alignement manuel CATSS.

Le projet prolonge Robert-Hayek, D'Amico et Rey, *A Deep Learning-Based Word
Alignment for the comparison of the Greek and Hebrew Bible* (CHR 2024) : il
reproduit l'approche SimAlign + mBERT, la compare à d'autres modèles (XLM-R,
Glot500) et à un LLM local, et l'évalue sur tout le gold CATSS au lieu de trois
chapitres alignés à la main.

## Données

| Rôle | Source | Dossier |
|---|---|---|
| Texte hébreu | BHSA 2021 (ETCBC, codex de Leningrad), via Text-Fabric | `data/he/` |
| Texte grec | Septante de Rahlfs 1935 (CenterBLC), via Text-Fabric | `data/lxx/` |
| Référence (gold) | CATSS, *Parallel Aligned Hebrew-Aramaic and Greek Texts* (Tov) | `data/gold/` (brut), `data/gold_clean/` (nettoyé) |

Les textes sont exportés par verset en couches parallèles : `t` (texte
original), `w` (un token par mot BHSA, proclitiques séparés), `l` (lexème),
`g` (numéro du mot graphique). Les choix de traitement (qere, noms composés,
doubles textes de Rahlfs, balisage CATSS…) sont justifiés dans
[DECISIONS.md](DECISIONS.md).

> **Licence des données.** Les données CATSS sont soumises aux conditions
> d'utilisation du CCAT, qui limitent leur redistribution. Vérifier ces
> conditions avant de rendre le dépôt public.

## Installation

Python 3.11 ou plus récent (testé avec 3.13).

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` contient tout : Text-Fabric, PyYAML, SimAlign avec
`sentencepiece` (nécessaire pour Glot500), eflomal (extension C, compilée à
l'installation).

**eflomal sur Mac.** eflomal se compile avec OpenMP, que le clang d'Apple ne
gère pas (`unsupported option '-fopenmp'`), et son Makefile demande la
bibliothèque GNU `gomp` (`library 'gomp' not found`). Compiler avec le clang de
Homebrew et faire passer `libomp` pour `gomp` le temps de la compilation :

```
brew install llvm libomp
export CC="$(brew --prefix llvm)/bin/clang"
mkdir -p /tmp/gomp && ln -sf "$(brew --prefix libomp)/lib/libomp.dylib" /tmp/gomp/libgomp.dylib
export LIBRARY_PATH=/tmp/gomp
pip install --no-cache-dir eflomal
```

Le programme compilé utilise ensuite directement `libomp` ; `/tmp/gomp` peut
être supprimé.

Les modèles Hugging Face (mBERT, XLM-R, Glot500) sont téléchargés au premier
lancement. Pour l'aligneur LLM : installer [Ollama](https://ollama.com) et un
modèle (`ollama pull gemma4:12b`).

## Préparer les données

Les données préparées sont déjà dans le dépôt. Pour les régénérer :

```
cd data
python export_bhsa_tf.py         # -> data/he/
python export_lxx_tf.py          # -> data/lxx/
cd ..
python src/gold_clean.py         # data/gold/ -> data/gold_clean/
```

Les cas du balisage CATSS encore non résolus sont listés dans
[TODO_gold_clean.md](TODO_gold_clean.md).

## Lancer une expérience

Une expérience est décrite par un fichier YAML dans `experiments/` :

```yaml
name: glot500_formes_sans_accents   # dossier des résultats : results/<name>/

passages:                           # livre hébreu, livre grec s'il diffère, chapitre
  - {book: Gen, only: Gen.1}
  - {book: Gen, only: Gen.3}
  - {book: 1Sam, only: 1Sam.9}
  # - {book: Judg, lxx_book: JudgA}  # doubles textes de Rahlfs

tokens: w                # w = formes, l = lemmes
greek_accents: false     # retirer les accents grecs

aligner: simalign        # simalign ou llm
model: cis-lmu/glot500-base   # bert (mBERT), xlmr, ou nom d'un modèle Hugging Face
layer: 8                 # couche du modèle
methods: mai             # m = mwmf, a = inter (argmax), i = itermax
device: cpu              # cpu, mps (GPU Apple), cuda

# pour aligner: llm
# llm_model: gemma4:12b
# llm_url: http://localhost:11434
# llm_think: false       # true = le modèle « réfléchit » avant de répondre (beaucoup plus lent)

```

Une seule commande :

```
python src/run.py experiments/glot500_formes_sans_accents.yaml
```

La configuration est vérifiée au démarrage : une option inconnue ou une
valeur invalide arrête le programme avant tout calcul.

### Résultats

Dans `results/<name>/` :

| Fichier | Contenu |
|---|---|
| `config.yaml` | copie de la configuration utilisée (reproductibilité) |
| `<passage>.jsonl` | alignements, une ligne par verset |
| `<passage>.csv` | relecture : un mot hébreu par ligne, mots grecs alignés, bloc CATSS, verdict (`juste`, `faux`, `non aligné`…) ; s'ouvre dans Excel ou Numbers |
| `scores.csv`, `scores.json` | mesures par passage et au total (et comptes bruts dans le JSON) |

Relire un verset dans le terminal :

```
python src/show.py results/glot500_formes_sans_accents/Gen.1.jsonl Gen.1.1 inter
```

## Évaluation

CATSS aligne des **blocs** (un mot graphique hébreu ↔ un groupe de mots grecs),
pas des mots isolés. Un lien proposé est donc jugé **juste** s'il reste à
l'intérieur d'un même bloc CATSS. Mesures :

- **précision** : liens justes / liens proposés ;
- **rappel par bloc** : blocs où au moins un lien juste a été trouvé / blocs à trouver ;
- **F1** : moyenne harmonique des deux ;
- **non-alignements respectés** : mots sans équivalent (plus et minus) laissés sans lien ;
- **AER** : taux d'erreur standard, à titre indicatif.

Détail de l'algorithme : [DECISIONS.md](DECISIONS.md), « Évaluation par blocs CATSS ».

### Résultats actuels

Gen 1, Gen 3, 1 Sam 9 ; formes, grec sans accents ; méthode `inter` (argmax).

| Aligneur | Précision | Rappel blocs | Non-alignements |
|---|---|---|---|
| mBERT | 73,0 % | 57,4 % | 75,0 % |
| XLM-R | 62,2 % | 44,2 % | 80,9 % |
| Glot500 | 82,8 % | 69,4 % | 87,5 % |
| Gemma 4 12B (LLM local, Gen 3 seulement) | 94,1 % | 94,4 % | 22,7 % |

Le LLM n'est pas déterministe, même à température 0 avec une graine fixe :
ses scores varient légèrement d'une exécution à l'autre.

## Organisation du code

| Fichier (`src/`) | Contenu |
|---|---|
| `config.py` | `Config`, `Passage` : lecture et vérification du YAML |
| `corpus.py` | `Corpus`, `Verse` : textes exportés et leurs couches |
| `aligners.py` | `Aligner` (interface commune), `SimAlignAligner`, `make_aligner` |
| `llm_align.py` | `OllamaAligner` : LLM local, tableau → liens |
| `gold.py` | `Gold` : unités CATSS, rattachement des tokens aux blocs |
| `evaluate.py` | `Evaluator` : jugement des liens, mesures, CSV de relecture |
| `experiment.py` | `Experiment` : enchaîne alignement, évaluation, écriture |
| `align.py` | parcours des versets d'un passage, écriture du JSONL |
| `normalize.py` | normalisation des tokens (voyelles, accents) |
| `gold_clean.py` | nettoyage du balisage CATSS |
| `run.py`, `show.py` | lignes de commande |

Ajouter une méthode d'alignement : écrire une sous-classe d'`Aligner`
(`align(verset hébreu, verset grec)`) et la déclarer dans `make_aligner`.

## Tests

```
python -m unittest discover -s tests       # tests unitaires
python tests/check_non_regression.py       # non-régression
```

Le contrôle de non-régression compare le code actuel aux résultats de
référence de `tests/reference/` (expériences de `experiments/`) : il réévalue
les alignements enregistrés (rapide, sans modèle) et, si les expériences
SimAlign ont été relancées, vérifie que leurs fichiers sont identiques.

## Documentation du projet

- [DECISIONS.md](DECISIONS.md) : journal des décisions (données, évaluation,
  architecture), rédigé pour servir de base à la section « Méthode » de l'article ;
- [TODO.md](TODO.md) : pistes et expériences à venir ;
- [TODO_gold_clean.md](TODO_gold_clean.md) : points restants du nettoyage CATSS.
