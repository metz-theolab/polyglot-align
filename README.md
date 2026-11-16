# 📜 polyglot-align : alignement mot à mot de la Bible hébraïque et de la Septante

**polyglot-align** est un paquet Python d'alignement automatique, mot à mot,
du texte hébreu de la Bible (BHSA) et de sa traduction grecque, la Septante
(Rahlfs). Les alignements sont évalués contre l'alignement manuel CATSS.

Le paquet propose une interface commune à plusieurs méthodes d'alignement :

* **SimAlign** : alignement par plongements multilingues (mBERT, XLM-R,
  Glot500), voir [SimAlign](https://github.com/cisnlp/simalign) ;
* **eflomal** : aligneur statistique, appris sur tout le corpus, voir
  [eflomal](https://github.com/robertostling/eflomal) ;
* **LLM local** : un modèle servi par [Ollama](https://ollama.com) (ex.
  Gemma 4 12B) aligne le verset sous forme de tableau.

Le projet prolonge Robert-Hayek, D'Amico et Rey, *A Deep Learning-Based Word
Alignment for the comparison of the Greek and Hebrew Bible* (CHR 2024) : il
reproduit l'approche SimAlign + mBERT, la compare à d'autres modèles et
méthodes, et l'évalue sur tout le gold CATSS (22 489 paires de versets) au lieu
de trois chapitres alignés à la main.

---

## 🛠️ Installation

Python 3.10 ou plus récent (testé avec 3.13). Depuis la racine du dépôt :

```bash
python -m venv venv
source venv/bin/activate
pip install -e '.[all]'
```

`[all]` installe tout. On peut n'installer que ce qui sert :

| Extra | Contenu |
|---|---|
| `simalign` | SimAlign, avec torch, transformers et `sentencepiece` (tokeniseur de Glot500) |
| `eflomal` | eflomal (extension C, compilée à l'installation) |
| `report` | matplotlib, pour les figures du rapport |
| `export` | Text-Fabric, pour régénérer les textes de `data/` |
| `dev` | flake8 |

Exemple : `pip install -e '.[eflomal,report]'`. Les versions minimales sont
dans `pyproject.toml`.

Les modèles Hugging Face (mBERT, XLM-R, Glot500) sont téléchargés au premier
lancement. Pour l'aligneur LLM : installer [Ollama](https://ollama.com) puis
un modèle (`ollama pull gemma4:12b`) ; aucun paquet Python n'est nécessaire.

<details>
<summary><b>eflomal sur Mac</b> (erreur <code>-fopenmp</code> ou <code>library 'gomp' not found</code>)</summary>

eflomal se compile avec OpenMP, que le clang d'Apple ne gère pas, et son
Makefile demande la bibliothèque GNU `gomp`. Compiler avec le clang de
Homebrew et faire passer `libomp` pour `gomp` le temps de la compilation :

```bash
brew install llvm libomp
export CC="$(brew --prefix llvm)/bin/clang"
mkdir -p /tmp/gomp && ln -sf "$(brew --prefix libomp)/lib/libomp.dylib" /tmp/gomp/libgomp.dylib
export LIBRARY_PATH=/tmp/gomp
pip install --no-cache-dir eflomal
```

Le programme compilé utilise ensuite directement `libomp` ; `/tmp/gomp` peut
être supprimé.
</details>

---

## 🚀 Utilisation

### 1️⃣ Ligne de commande

Une expérience est décrite par un fichier YAML dans `experiments/` :

```yaml
name: glot500_vocalized        # dossier des résultats : results/<name>/

passages:                      # livre hébreu ; livre grec s'il diffère ; chapitre ou verset
  - {book: Gen}                # tout le livre
  - {book: Gen, only: Gen.3}   # un chapitre
  - {book: Judg, lxx_book: JudgA}   # doubles textes de Rahlfs

# texte donné à l'aligneur (options comprises par tous les aligneurs)
tokens: w            # w = mots BHSA (בְּ רֵאשִׁית), g = mots graphiques (בְּרֵאשִׁית), l = lemmes
hebrew: vocalized    # pointed = tel qu'exporté, vocalized = voyelles, unvocalized = consonantique
greek: unaccented    # accented, unaccented = accents et esprits retirés, minuscules

aligner:             # méthode et ses options propres
  type: simalign     # simalign | eflomal | llm
  model: cis-lmu/glot500-base   # bert (mBERT), xlmr, ou nom d'un modèle Hugging Face
  bert_layer: 8      # couche du modèle
  methods: mai       # m = mwmf, a = inter (argmax), i = itermax
  device: cpu        # cpu, mps (GPU Apple), cuda
```

Options des autres aligneurs :

```yaml
aligner:
  type: eflomal      # aucune option propre ; symétrisations inter et gdfa

aligner:
  type: llm
  model: gemma4:12b              # obligatoire
  url: http://localhost:11434
  think: false       # true = le modèle « réfléchit » avant de répondre (beaucoup plus lent)
  seed: 1
```

Une seule commande aligne, évalue et écrit les résultats :

```bash
polyglot-align run experiments/glot500_vocalized.yaml
```

* La configuration est vérifiée au démarrage : une option inconnue ou une
  valeur invalide arrête le programme avant tout calcul.
* Une expérience interrompue **reprend** où elle s'était arrêtée quand on la
  relance (les versets déjà alignés sont sautés).
* Un dossier `results/<name>/` produit par une **autre** configuration n'est
  pas écrasé : changer `name`, ou repartir de zéro avec `--force`.

Résultats dans `results/<name>/` :

| Fichier | Contenu |
|---|---|
| `config.yaml` | copie de la configuration utilisée |
| `<passage>.jsonl` | alignements, une ligne par verset |
| `<passage>.csv` | relecture : un mot hébreu par ligne, mots grecs alignés, bloc CATSS, verdict (`juste`, `faux`, `non aligné`…) ; s'ouvre dans Excel ou Numbers |
| `scores.csv`, `scores.json` | mesures par passage et au total (comptes bruts dans le JSON) |
| `perf.json` | durée et temps CPU par phase, coût en s / 1 000 versets, débit, mémoire maximale, machine et versions des bibliothèques |

Autres commandes :

```bash
polyglot-align show results/glot500_vocalized/Gen.jsonl Gen.1.1 inter   # relire un verset
polyglot-align report reports/article.yaml                               # tableaux et figures
polyglot-align clean-gold                                                # data/gold -> data/gold_clean
polyglot-align --help
```

`python -m polyglot_align …` fait la même chose sans passer par la commande
installée.

### 2️⃣ API Python

Les mêmes objets s'utilisent directement, sans fichier de configuration :

```python
from polyglot_align.store import DataStore
from polyglot_align.aligners.eflomal import EflomalAligner

store = DataStore("data")          # textes, gold et table des versets, lus une fois

aligner = EflomalAligner(layer="w", hebrew="unvocalized", greek="unaccented")
aligner.fit(store.table_pairs())   # eflomal apprend sur les 22 489 paires (quelques secondes)

(hv, gv), = store.verse_pairs("Gen", "Gen", only="Gen.1.1")
res = aligner.align(hv, gv)
for i, j in sorted(res.links["inter"]):
    print(res.src[i], "↔", res.tgt[j])     # ב ↔ εν, ראשית ↔ αρχη, ברא ↔ εποιησεν…
```

Tous les aligneurs ont la même interface : `fit(paires de versets)` (ne fait
rien pour SimAlign et le LLM), puis `align(verset hébreu, verset grec)`, qui
renvoie les tokens montrés (`src`, `tgt`) et les liens par méthode (`links`).

Une expérience complète depuis Python :

```python
from polyglot_align.experiment import Experiment

scores = Experiment.from_yaml("experiments/eflomal_unvocalized.yaml").run()
print(scores["TOTAL"]["methodes"]["inter"]["mesures"])
```

La bibliothèque n'affiche rien elle-même : elle écrit dans le journal
`logging` (`polyglot_align`), que la ligne de commande affiche.

### 3️⃣ Reproduire les résultats

Les expériences sur toute la Bible (39 livres hébreux, Abdias exclu faute de
paires dans la table ; hébreu vocalisé ou non) :

```bash
for e in eflomal glot500 mbert xlmr; do
  for v in unvocalized vocalized; do
    polyglot-align run experiments/${e}_${v}.yaml
  done
done
polyglot-align report reports/article.yaml   # -> reports/article/
```

Durées mesurées sur un Mac (CPU, `perf.json`, apprentissage + alignement) :
eflomal, quelques secondes (plus le chargement des données) ; SimAlign, de 26
min (Glot500 non vocalisé) à 3 h 16 (mBERT vocalisé) par expérience. `reports/article.yaml` choisit les expériences, méthodes et
colonnes de chaque tableau et les figures ; le rapport lit seulement les
`results/<nom>/` existants et produit les tableaux en `.tex` (booktabs), `.md`
et `.csv`, et les figures en `.pdf` et `.png`. Les exécutions répétées
`<nom>_run1`, `<nom>_run2`… sont regroupées (moyenne ± écart-type).

---

## 📚 Données

| Rôle | Source | Dossier |
|---|---|---|
| Texte hébreu | BHSA 2021 (ETCBC, codex de Leningrad), via Text-Fabric | `data/he/` |
| Texte grec | Septante de Rahlfs 1935 (CenterBLC), via Text-Fabric | `data/lxx/` |
| Référence (gold) | CATSS, *Parallel Aligned Hebrew-Aramaic and Greek Texts* (Tov) | `data/gold/` (brut), `data/gold_clean/` (nettoyé) |

Les textes sont exportés par verset en couches parallèles : `t` (texte
original), `w` (un token par mot BHSA, proclitiques séparés), `l` (lexème),
`g` (numéro du mot graphique). `data/lxx/` ne contient que les 40 livres
alignables (dont les doubles textes `JoshA`, `JudgA`, `DanTh`) ; les livres
grecs sans équivalent hébreu sont dans `data/lxx/non_aligned/`.

Les versets sont appariés par la **table d'équivalence** `data/verse_map.json`,
tirée du gold : un verset hébreu n'est aligné qu'avec son équivalent LXX
(Ps 23:1 TM ↔ Ps 22:1 LXX, chapitres déplacés de Jérémie…), et seuls les
groupes 1 verset ↔ 1 verset sont gardés (22 489 paires, 97,6 % des groupes).
Les choix de traitement (qere, noms composés, doubles textes de Rahlfs,
balisage CATSS…) sont justifiés dans [DECISIONS.md](DECISIONS.md).

Les données préparées sont dans le dépôt. Pour les régénérer :

```bash
cd data && python export_bhsa_tf.py && python export_lxx_tf.py && cd ..   # -> data/he, data/lxx
polyglot-align clean-gold                                                  # -> data/gold_clean
cd data && python make_verse_map.py && cd ..                               # -> data/verse_map.json
```

> **Licence des données.** Les données CATSS sont soumises aux conditions
> d'utilisation du CCAT, qui limitent leur redistribution. Vérifier ces
> conditions avant de rendre le dépôt public.

---

## 📏 Évaluation

CATSS aligne des **blocs** (un mot graphique hébreu ↔ un groupe de mots grecs),
pas des mots isolés. Un lien proposé est donc jugé **juste** s'il reste à
l'intérieur d'un même bloc CATSS. Mesures :

* **précision** : liens justes / liens proposés ;
* **rappel par bloc** : blocs où au moins un lien juste a été trouvé / blocs à trouver ;
* **F1** : moyenne harmonique des deux ;
* **non-alignements respectés** : mots sans équivalent (plus et minus) laissés sans lien ;
* **AER** : taux d'erreur standard, à titre indicatif.

Les mesures sont des moyennes micro (calculées sur les comptes, jamais en
moyennant des pourcentages). Détail de l'algorithme : [DECISIONS.md](DECISIONS.md),
« Évaluation par blocs CATSS ».

### Résultats actuels

Toute la Bible (22 489 paires de versets), mots BHSA, grec sans accents,
méthode `inter` (sauf mention `gdfa`) :

| Aligneur | Hébreu | Précision | Rappel blocs | F1 | Non-alignements |
|---|---|---:|---:|---:|---:|
| mBERT | non vocalisé | 66,3 % | 52,1 % | 58,3 % | 68,3 % |
| mBERT | vocalisé | 51,3 % | 50,3 % | 50,8 % | 58,3 % |
| XLM-R | non vocalisé | 56,1 % | 40,6 % | 47,1 % | 74,6 % |
| XLM-R | vocalisé | 34,5 % | 24,0 % | 28,3 % | 71,9 % |
| Glot500 | non vocalisé | 79,6 % | 67,4 % | 73,0 % | 78,2 % |
| Glot500 | vocalisé | 81,4 % | 72,4 % | 76,6 % | 76,0 % |
| eflomal | non vocalisé | **97,4 %** | 93,0 % | 95,2 % | **86,7 %** |
| eflomal | vocalisé | **97,4 %** | 92,3 % | 94,8 % | 86,6 % |
| eflomal (`gdfa`) | non vocalisé | 94,0 % | **97,3 %** | **95,6 %** | 68,5 % |
| eflomal (`gdfa`) | vocalisé | 93,6 % | 97,0 % | 95,3 % | 67,1 % |

Les scores d'eflomal baissent dans les livres traduits librement : Esther
(F1 80,2 %), Daniel OG (83,8 %), Job (84,5 %), Proverbes (86,6 %), Isaïe
(90,5 %).

Ni eflomal ni le LLM ne sont déterministes (le LLM même à température 0 avec
une graine fixe) : leurs scores varient légèrement d'une exécution à l'autre
(eflomal, Genèse : F1 de 95,7 à 95,9 % sur trois exécutions). Les chiffres
ci-dessus viennent d'une seule exécution.

---

## 🧩 Organisation du code

Paquet `polyglot_align` (`src/polyglot_align/`) :

| Module | Contenu |
|---|---|
| `config.py` | `Config`, `Passage` : lecture et vérification du YAML (l'ancien format plat est converti) |
| `corpus.py` | `Corpus`, `Verse` : textes exportés et leurs couches ; `VerseMap` : table d'équivalence des versets |
| `store.py` | `DataStore` : seul accès à `data/`, chaque fichier lu une fois |
| `normalize.py` | normalisation des tokens (vocalisation, accents) ; rattachement lettre par lettre |
| `alignment.py` | `VerseAlignment`, `AlignmentRecord` : résultat d'un aligneur, format JSONL |
| `aligners/` | `Aligner` (interface commune) ; `simalign.py`, `eflomal.py`, `llm.py` ; registre `ALIGNERS` |
| `evaluation/` | `Gold` (unités CATSS), `Evaluator` (jugement des liens, mesures, CSV), `gold_clean` (nettoyage du balisage CATSS) |
| `experiment.py` | `Experiment` : enchaîne apprentissage, alignement, évaluation, écriture ; reprise |
| `align.py` | parcours des versets d'un passage, écriture du JSONL verset par verset |
| `perf.py` | `PerfMeter` : durée, temps CPU, mémoire et débit par phase → `perf.json` |
| `report.py` | tableaux et figures pour l'article, à partir de `results/` |
| `cli.py`, `show.py` | ligne de commande `polyglot-align` |

**Ajouter une méthode d'alignement** : écrire une sous-classe d'`Aligner` dans
`aligners/`, qui déclare `name` (valeur de `type` dans la config), `PARAMS`
(ses options et leurs valeurs par défaut) et, au besoin, `check_params` ;
implémenter `align(verset hébreu, verset grec)`, et `fit(paires de versets)`
si la méthode apprend sur le corpus ; l'ajouter au registre `ALIGNERS`
(`aligners/__init__.py`). La normalisation commune (`hebrew`, `greek`) est
fournie par `Aligner.normalized_tokens`.

---

## 🧪 Tests

```bash
python -m unittest discover -s tests       # tests unitaires
python tests/check_non_regression.py       # non-régression
flake8                                     # style (configuration : .flake8)
```

Le contrôle de non-régression réévalue, avec le code actuel, les alignements
de référence enregistrés dans `tests/reference/` (rapide, sans modèle) : les
liens, les scores et les CSV de relecture doivent être identiques.

---

## 📖 Documentation du projet

[DECISIONS.md](DECISIONS.md) : journal des décisions (données, évaluation,
architecture), rédigé pour servir de base à la section « Méthode » de
l'article.
