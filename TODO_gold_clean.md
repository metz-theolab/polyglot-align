# Nettoyage du gold CATSS : points à régler

Script : [src/gold_clean.py](src/gold_clean.py) · tests : [tests/test_gold_clean.py](tests/test_gold_clean.py)
· sortie : `data/gold_clean/<livre>.json` (noms OSIS des exports : `1Chr.json`,
`Eccl.json`…) · compteurs : `data/gold_clean/_rapport.json`

Chaque cas non décidé est marqué dans la sortie par un champ `todo` (nom entre
parenthèses ci-dessous) ; la forme brute est toujours conservée (`raw_hb`,
`raw_gr`). Pour retrouver les exemples d'un cas : chercher son nom de `todo`
dans `data/gold_clean/*.json`.

Chiffres : exécution du 2026-11-09, 347 966 unités au total.

Une fois un point tranché : l'inscrire dans [DECISIONS.md](DECISIONS.md),
adapter le script, ajouter un test, relancer `python src/gold_clean.py`.

---

## A. Règles appliquées par défaut, à valider

Déjà dans le code, mais absentes de DECISIONS.md.

- [ ] **A1. `{..pX}` et `{..dX}` : X gardé dans le texte** (1 527 et 580 unités).
  Le code de l'indicateur est noté dans `flags` (`..p`, `..d`).
  Ex. 1 Ch 4:31 `καὶ {..dἐν} βαιθμαρχαβωθ` → `καὶ ἐν βαιθμαρχαβωθ`
  (`ἐν` est bien dans le texte de Rahlfs).
  Note : l'inventaire de DECISIONS.md comptait `{p}` 290 et `{..p}` 1 ; il
  n'avait pas vu les formes avec contenu.
  → fonction `clean_side`, `inline()`.

- [ ] **A2. `,,a` (passage araméen) : marqueur retiré, noté `arameen`**
  (10 340 unités). Ex. Esd 4:8 `רחום ,,a`.
  A corrigé 2 376 unités `--+ ,,a` qui passaient à tort pour des alignements
  (ex. DanTh 2:6 `--+ ,,a` ↔ `μοι` est un plus).

- [ ] **A3. `#` en début d'unité : suite de la ligne précédente, fusion avec
  l'unité précédente** (≈ 340 unités). Ex. 2 S 2:8 #15 `#` ↔ `παρεμβολῆσ}`.
  → fonction `merge_hash`.

- [ ] **A4. Notes hors colonne b (`.bm`, `<sp>`) côté hébreu : supprimées.**
  Ex. 1 Ch 4:31 #6 `# .bm`.

## B. Problèmes à régler

### B1. Ben Sira (`ben_sira_balisage_propre`) — 14 029 unités, tout le livre

Balisage propre : numéros des manuscrits hébreux.
Ex. Sir 7:20 `תדע 3 תרע* {4}` ; Sir 3:15 `צרה {3} >4`.

- [ ] Exclure Ben Sira de la première version ? (C'est de toute façon
  l'ensemble de test de généralisation.)
- [ ] Plus tard : définir la règle (quel manuscrit garder, que faire des
  variantes).

### B2. Références LXX non lues (`ref_lxx_forme`) — 6 666 unités

Seules les formes `[6]` et `[1.7]` sont lues ; pour les autres, `ref_lxx`
reste égal à `ref_mt`.

- [ ] **1 Esdras : `[e1.1]` (3 761), `[cc35.1]` (763), `[ne 7.72]` (258).**
  Ex. 1 Esd 1:1 `καὶ ἤγαγεν [cc35.1]`.
  Hypothèse : sens **inversé**. La clé CATSS est la référence grecque (1 Esd),
  le crochet renvoie au parallèle hébreu (`cc` = 2 Chroniques, `e` = Esdras,
  `ne` = Néhémie). Il faut alors `ref_lxx` = clé et `ref_mt` = crochet.
  À vérifier aussi : avec quel fichier BHSA aligner 1 Esdras.

- [ ] **Versets additionnels avec lettre** (≈ 700) : `[16a]`, `[2.46g]`,
  `[12.24m]`, `[1.1s]`.
  Ex. 1 R 5:5 `καὶ κατῴκει [2.46g]` ; Est 1:1 `καὶ ἐγένετο [1.1s]`.
  Additions de la LXX (3 R 2:35a–o, 2:46a–l, 12:24a–z, additions d'Esther…).
  À vérifier : comment CenterBLC numérote ces versets (trait `subverse` ?).

- [ ] **Doubles crochets `[[14]]`, `[[16.6]]`, `[[50b]]`** (833).
  Ex. 2 S 5:16 `{...}` ↔ `σαμαε [[14]]` ; Prov 15:27 `{...}` ↔
  `ἐλεημοσύναις [[16.6]]`. Sens inconnu (doublet placé ailleurs ?) :
  consulter la documentation CATSS.

- [ ] **Plusieurs références** : 1 R 3:1 `[2.35c,5.14a]`.

- [ ] **Crochet non fermé** (33, coquilles) : Ps 106:39 `… αὐτῶν [105.3`.

### B3. Renvois vides non rattachés (`renvoi_vide_non_rattache`) — 3 348 unités

Unité `{...}` sans indication de l'unité visée.
Ex. Qo 7:22 #7 `{...}` ↔ `πολλας` ; Qo 7:24 #3 `שׁהיה` ↔ `{...}`.
Actuellement : l'autre côté reste non aligné.

- [ ] Chercher à les rattacher (règle à définir) ou accepter le non-alignement ?

### B4. Transpositions non résolues — 856 unités

- [ ] **Côté grec** (`transposition_grecque_non_resolue`, 687) : le mot
  transposé fait plusieurs mots, ou l'unité d'arrivée n'est pas un simple
  `{...}`. Ex. 1 Ch 9:31 `--+ הגדול` ↔ `{..^τοῦ μεγάλου}` ;
  2 S 17:3 `אשׁר =אחד` ↔ `{..^ἑνὸσ}`.
- [ ] **Côté hébreu** (`transposition_hebraique_non_resolue`, 169) : l'unité
  d'arrivée ne contient pas seulement `^^^`. Ex. 2 S 3:36 `^^^ ^ =ויכר` ↔
  `{...καὶ} ἔγνω` ; 1 Ch 28:17 `^^^ ^ =ובמשׁקל`.
- [ ] Élargir la règle de recherche, ou traiter à la main ?
- [ ] `{..^X}` côté hébreu (218, signalé dans DECISIONS.md) : même règle en
  miroir ? `X^X` collé dans un mot hébreu (164) ?

### B5. Indicateurs hébreux avec contenu — 416 unités

- [ ] **`{..rX}`** (`indicateur_..r_hb`, 364 ; 5 côté grec).
  Ex. Os 1:7 `ובחרב {..rלא}` ↔ `οὐδὲ ἐν ῥομφαίᾳ` : le `לא` d'un mot voisin
  semble rendu ici par `οὐδέ`. En faire un lien *possible*, comme `{...X}` ?
- [ ] **`{..?X}`** (`indicateur_.._hb`, 47). Ex. 1 Ch 27:6 `{..?על} ומחלקתו`.
- [ ] **`{..dX}` côté hébreu** (4).

### B6. Résidus de balisage (`residu_hb`, `residu_gr`) — ≈ 3 785 unités

| Cas | Unités | Exemple | Question |
|---|---|---|---|
| `{---%}` | 1 339 | Jb 2:1 `παραστῆναι {---%}` | Job seulement : astérisque hexaplaire (texte ajouté d'après Théodotion) ? |
| `{cX}` | 526 | Qo 2:2 `περιφοραν {cπαραφοραν}` | Leçon corrigée / variante : garder X ou le supprimer ? |
| `?` côté hébreu | 209 | Qo 7:17 `למה --+ ?` | Marque d'incertitude : supprimer ? |
| `{d?}` côté hébreu | 32 | 2 S 24:23 `המלך {d?}` | Doublet incertain : comme `{d}` ? |
| `--` côté hébreu | 81 | 1 Ch 11:20 `-- =בפעם אחת` | Variante de `--+` ? |
| grec avec trait d'union | 60 | Os 1:9 `οὐ-λαόσ-μου` | Couper pour suivre la tokenisation CenterBLC (`οὐ λαός μου`) ? |
| `^δὲ` collé | 24 | Is 51:6 `ἡ ^δὲ γῆ` | Coquille : traiter comme `^ δὲ` ? |
| `*X*` (Psaumes) | ? | Ps 56:7 `*יצפינו* *יצפונו` | Autre notation du ketiv/qere ? |
| `^?` côté hébreu | 9 | Ps 22:20 `אילותי ^? =עזרתי` | ? |
| `,` dans un mot hébreu | 18 | 2 S 19:18 `{..rעמו,אתו}` | Alternatives : lesquelles garder ? |

### B7. Petits cas, un par un

- [ ] **Ketiv sans qere** (`ketiv_sans_qere`, 4) : pas de forme lue, donc pas
  de token BHSA ; l'équivalent grec devient-il non aligné ?
- [ ] **Renvois hors verset** (`renvoi_hors_verset`, 391) : conformes à
  DECISIONS.md (non alignés) ; vérifier quelques cas.
  Ex. 2 S 5:14 `σαμμους {d} {...σαμαε} [16a]`.
- [ ] **Esdras–Néhémie** : le gold a `Ezra.json` et `Neh.json` (découpage du
  TM, comme BHSA), la LXX un seul livre `2Esdr` (Esdras B). Pour l'évaluation,
  il faut une correspondance Ezra/Neh → 2Esdr (chapitres de Néhémie décalés
  dans 2Esdr). À vérifier : les crochets `[ ]` de ces fichiers donnent-ils
  déjà la référence 2Esdr ?
- [ ] **Marqueurs de la liste CATSS absents des fichiers** (`~~~`, `{..d}`,
  `{..r}`, `..a`, `{#}`) : vérifier sur les fichiers CATSS d'origine
  (déjà noté dans DECISIONS.md).

## C. Pour l'évaluation (`evaluate.py`)

- [ ] Décider : liens `possible` neutralisés (ni justes ni faux), comme dans
  l'AER, ou ignorés ?
- [ ] Décider : évaluation au niveau de l'unité (un lien est juste si les deux
  mots sont dans la même unité `sure` de type `align`) ; lien touchant un plus
  ou un minus = faux.
- [ ] Décider : unités avec `todo` exclues du calcul (mots ignorés), en
  indiquant la part du gold évaluée.
- [ ] Définir le rappel : par unité (au moins un lien interne trouvé) et/ou par
  mot (mot relié à un mot de son unité).
- [ ] Relier les unités aux tokens : BHSA par `g` (mots graphiques), CenterBLC
  par `ref_lxx` (voir « Pièges connus » dans DECISIONS.md).
