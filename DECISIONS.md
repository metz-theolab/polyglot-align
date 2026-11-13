# Décisions de conception

Journal des décisions prises en discussion « brainstorming ».
Chaque entrée : date, décision, raison, statut (`décidé` / `à trancher`).

---

## 2026-11-06 — Normalisation du gold standard : module séparé

**Statut : décidé**

Le nettoyage du gold (`data/gold/*.json`) se fait dans un module indépendant
(`gold_clean.py`, à écrire) qui produit un JSON propre, versionné, dans
`data/gold_clean/`. Le code d'alignement (`align.py`) n'a pas à connaître le
balisage du gold.

**Raison :** le balisage du gold encode des choix philologiques (plus, minus,
rétroversions, transpositions). Ces choix doivent être faits une fois,
documentés et relisibles, pas recalculés à chaque exécution.

**Principes du format nettoyé :**
- champs explicites (`type`, `retro`, `transp`…) au lieu du balisage ;
- toujours conserver la forme brute (`raw_hb`, `raw_gr`) pour pouvoir
  revenir sur une décision en relançant le script.

## 2026-11-06 — Tokenisation partagée

**Statut : décidé**

`norm_heb` et `norm_grc` sortent de `align.py` vers un module
`src/normalize.py`, importé à la fois par `align.py` et par l'évaluation.
La tokenisation vient de l'export (couche `w`, mots BHSA) : `normalize.py` ne
fait que nettoyer chaque token, sans en ajouter ni en retirer. La tokenisation
Stanza (`hbo`) est abandonnée (2026-11-09) : elle introduisait des erreurs de
segmentation (Gn 1:2 `ובהו` → `ו ב הו`) que la segmentation BHSA n'a pas.

**Raison :** pour évaluer, liens gold et liens SimAlign doivent porter sur les
mêmes indices de tokens. Le gold est projeté dans la tokenisation de
l'aligneur, pas l'inverse.

## 2026-11-08 — Format d'export des textes : couches parallèles par verset

**Statut : décidé**

Chaque verset est un objet à couches, chaque couche étant une chaîne de tokens
séparés par des espaces :

```json
{"Gen": {"1": {"1": {
  "t": "בְּרֵאשִׁ֖ית בָּרָ֣א …",
  "w": "בְּ רֵאשִׁ֖ית בָּרָ֣א …",
  "l": "ב ראשׁית ברא …",
  "g": "0 0 1 …"
}}}}
```

- `t` : texte original (non tokenisé) ;
- `w` : un token par mot BHSA, proclitiques séparés ;
- `l` : lexème consonantique (`lex_utf8`) de chaque token ;
- `g` : numéro du mot graphique de chaque token.

Règles :
-  `w`, `l` et `g` ont le même nombre de tokens ;
- aucun token ne contient d'espace;
- Le maqqef est remplacé par deux mots
- L'article seulement marqué par la vocalisation est ignoré dans les couches.
- Les noms propres composés (un seul mot BHSA avec un séparateur interne,
  **espace, maqqef ou paseq** : `בית אל`, `בית־אל`, `תובל קין`, `עשה־אל`,
  Jos 15:25 `חָצֹ֤ור׀ חֲדַתָּה֙`, seul cas avec paseq) deviennent un
  seul token avec `_` (`בית_אל`), quel que soit le séparateur, dans `w` comme
  dans `l`, et comptent pour un seul mot graphique dans `g`. Cette règle
  l'emporte sur celle du maqqef. `t` garde la graphie d'origine.
  Chiffres : 298 tokens à maqqef interne (ex. 1 Ch 2:16 `עֲשָׂה־אֵ֖ל`,
  Ps 110:4 `מַלְכִּי־צֶֽדֶק`), plus les noms écrits avec une espace
  (ex. Gen 4:22 `תובל קין`, `בית לחם` 41 occurrences du lexème).
  Raison : `בית אל` et `בית־אל` donnent le même token ; `w` et `l` utilisent le
  même séparateur (le lexème BHSA s'écrit avec une espace dans les deux cas).

**Raison :** `g` permet de reconstruire les mots graphiques et de relier
les tokens aux unités du gold CATSS (organisé par mots graphiques).
Morphologie (`m`) et syntaxe (`s`) pourront être ajoutées plus tard.

## 2026-11-08 — Doubles textes de Rahlfs (Josué, Juges)

**Statut : décidé**

CenterBLC donne les deux textes de Rahlfs sous la même référence, B puis A
(Juges en entier ; Jos 15:21-62, 18:21-28, 19:1-45). L'export LXX les sépare :
la 1re occurrence (B) reste dans `Josh` / `Judg`, la 2e (A) va dans `JoshA` /
`JudgA`, comme dans le gold CATSS (qui nomme le texte B `JoshB` / `JudgB`).

**Raison :** ne rien écraser (l'ancien export mélangeait B et A dans Josué et ne
gardait que A pour Juges) ; `Josh` / `Judg` s'apparient directement avec BHSA.
**Conséquence :** deux alignements à faire pour ces livres (voir TODO.md).

## 2026-11-08 — Ketiv / qere : le qere partout

**Statut : décidé**

Dans l'export BHSA, `t` et `w` donnent le **qere** quand il existe (`qere_utf8`),
sinon la forme écrite (`g_word_utf8`). `t` utilise le format `text-orig-full`
(qere), `w` doit faire de même. Les qere sans ketiv (2 R 19:31 `צבאות`) sont des
tokens ; un mot sans forme lue (ketiv sans qere, article caché) est ignoré dans
toutes les couches et ne compte pas comme mot graphique dans `g`. `l` ne change
pas (même lexème pour ketiv et qere).

**Raison :** CATSS ne choisit pas : chaque unité contient les deux formes
(`*ketiv **qere`, `*z` = pas de ketiv) et indique parfois laquelle suit le grec
(`{**}` qere : 290 unités ; `{*}` ketiv : 176 ; sans indication : 1 914).
Prendre le qere :
- couvre les qere sans ketiv, alignés avec le grec dans CATSS ;
- correspond au cas le plus fréquent quand CATSS tranche ;
- rend `t` et `w` cohérents.

Pour l'évaluation, le choix compte peu : l'unité CATSS contient les deux formes
et nos tokens y sont rattachés par `g`.

**Écartés :**
- choisir mot par mot d'après `{*}`/`{**}` : ce serait utiliser le gold pour
  construire l'entrée de l'aligneur (fuite à l'évaluation, impossible sur un
  texte sans gold) ;
- mettre les deux formes dans `w` (`xxx* yyy**`, comme CATSS) : doublons qui
  faussent la phrase vue par l'aligneur, lexème dupliqué dans `l`.

**Plus tard (optionnel) :** une couche `k` (ketiv, `-` si absent) pour étudier
les cas où le grec suit le ketiv, sans changer `w`.

## 2026-11-09 — Nettoyage du balisage CATSS : ne garder que l'alignement

**Statut : décidé** (sauf numérotation des versets et `{...}`, voir « À trancher »)

`gold_clean.py` retire toute l'annotation critique de CATSS et ne garde que
l'alignement hébreu ↔ grec. Mais certains marqueurs **sont** de l'information
d'alignement : ils sont interprétés, pas simplement effacés.

Chiffres : inventaire sur les 349 769 unités de `data/gold/` (46 fichiers).

**1. Plus et minus → non-alignement explicite.** Le symbole est retiré, l'unité
est gardée avec un côté vide : tokens grecs sans équivalent hébreu (plus), ou
hébreux sans équivalent grec (minus).
- `--+` (plus LXX) : 19 630 unités (ex. Qoh 1:1 `--+ =:ישׂראל` ↔ `ισραηλ`) ;
- `---` (minus LXX) : 16 959 unités côté grec (ex. Qoh 2:12 `כבר` ↔ `---`),
  75 côté hébreu (1 Ch 4:16 `---` ↔ `αμηαχι`) ;
- `''` (long plus/minus) : 8 467 unités côté hébreu, 7 790 côté grec
  (ex. 1 Ch 1:11 `ומצרים` ↔ `--- ''`).

Raison : ces tokens restent dans l'entrée de l'aligneur ; le gold doit dire
qu'ils ne s'alignent pas, sinon les faux liens qui les touchent ne sont pas
comptés. Cela permet aussi de mesurer la capacité de l'aligneur à *ne pas*
aligner (argmax vs itermax).
Écarté : supprimer ces unités (≈ 10 % du gold, et perte de toute mesure des
faux liens).

**2. `#` (ligne coupée) → fusion avant nettoyage.** 547 unités (ex. 1 Ch 4:31
`בראי ובשׁערים =:בראומשׁערים #`). Les deux moitiés sont recollées en une
unité. Écarté : nettoyer ligne par ligne (un bloc deviendrait deux unités
fausses).

**3. Colonne b (tout ce qui suit `=` côté hébreu) → supprimée.** 21 327 unités :
rétroversions (`=`, `=;`, `=:`, `=v`, `=@`, `=r`, `=+`), catégories de
technique de traduction (`=%…`), `G`, et les `?` qui s'y trouvent
(ex. Qoh 3:19 `ומותר =?ומה יתר .s`). Ce n'est pas du texte TM.

**4. Indicateurs → retirés de l'alignement, conservés comme métadonnées.**
`{t}` translittération (936 grec, 4 hébreu ; ex. Hos 3:2 `καὶ γομορ {t}`),
`{d}` doublet (1 058 grec, 581 hébreu), `{p}` préverbe grec = préposition
hébraïque (290 ; ex. 1 Ch 12:22 `{p} τῷ δαυιδ`), `{..p}` (1), `{*}`/`{**}`,
`{g}`, `{v}`, `{s}`, `{!}`, `~` (15 grec, 3 hébreu ; ex. Jon 1:5
`ιωνας ~ δὲ`). Gardés comme champs du JSON propre, avec `raw_hb`/`raw_gr`.
Raison : coût nul, et permet d'analyser les résultats par phénomène (ex. les
translittérations s'alignent-elles mieux ?).

**5. Ketiv / qere → le qere seul**, cohérent avec l'export BHSA (entrée
« Ketiv / qere : le qere partout »). 1 054 unités `*ketiv **qere`
(ex. Qoh 4:17 `*רגליך **רגלך {*}`) ; 14 unités `*z`
(ex. 2 S 8:3 `*z **פרת {**}`, qere sans ketiv → qere gardé). Ketiv sans
qere : pas de forme lue, donc pas de token BHSA ; cas à examiner un par un
(l'équivalent grec devient-il non aligné ?).

**Marqueurs de la liste CATSS absents des fichiers :** `~~~`, `{..d}`,
`{..r}`, `..a`, `{#}` (0 occurrence). Perdus à la conversion en JSON ou notés
autrement : à vérifier sur les fichiers CATSS d'origine (Job devrait
contenir des `{#}`). Présents mais absents de la liste : `^`
(Gn 1:2 `ἡ ^ δὲ γῆ`, 1 Esd 8:59 `{..^εἰσήνεγκαν}`) et `<x.y>`
(Gn 1:6 `--+ =;ויהי <1.7>`, en colonne b).

## 2026-11-09 — Numérotation des versets CATSS : champ `ref_lxx`

**Statut : décidé** (inventaire des formes de références à faire)

Chaque unité du gold propre porte deux références : `ref_mt` (la clé CATSS
actuelle, versification du TM) et `ref_lxx` (versification de la LXX, déduite
des marqueurs `[ ]` / `[[ ]]` ; égale à `ref_mt` en l'absence de marqueur).
L'évaluation va chercher les tokens CenterBLC par `ref_lxx`. Les marqueurs sont
ensuite retirés du texte.

Chiffres : `[ ]` sur 45 467 unités côté grec (ex. Qoh 1:5 `ἀνατέλλων [6]` : le
verset 6 de la LXX commence ici), 4 975 côté hébreu ; `[[ ]]` sur 887 unités
grecques, 10 hébraïques.

**Raison :** c'est la seule information qui relie CATSS (versification TM) aux
versets de CenterBLC (versification LXX).
**Écarté :** supprimer les marqueurs (il faudrait reconstruire la
correspondance des versets par une table externe, moins précise qu'unité par
unité).
**Reste à faire :** inventorier les formes avant d'écrire le parseur : `[6]`,
`[119.4]` (Psaumes), `[e8.30]` (1 Esdras), `[[14]]`, `[[nu33.18]]` (renvoi
vers un autre livre).

## 2026-11-09 — `{...}` (équivalent ailleurs) : lien reconstruit ou non-alignement

**Statut : décidé** (option B)

- Équivalent **dans le même verset** → le lien est reconstruit en *possible*
  (ex. Isa 48:17 : `בדרך` ↔ `ἐν αὐτῇ`, unités #13 et #15).
- Équivalent **hors du verset** (marqueur `[n]` sur l'unité, ou X introuvable
  dans le verset) → non aligné.
- L'unité `{...}` elle-même (simple renvoi) disparaît.

Chiffres : 6 294 unités côté hébreu, 745 côté grec.

| Cas | Hébreu | Grec |
|---|---|---|
| `{...X}`, X retrouvé dans le même verset | 1 076 | 1 670 |
| `{...X}`, X non retrouvé | 471 | 545 |
| `{...}` vide, avec changement de verset LXX `[n]` | 1 146 | 2 |
| `{...}` vide, sans changement de verset | 5 148 | 745 |

Exemples : Isa 48:17 #13 `בדרך` ↔ `ἐν ᾗ {...ἐν αὐτῇ}` et #15 `{...}` ↔
`ἐν αὐτῇ` (même verset) ; Zeph 3:15 #14 `{...לא} עוד` ↔ `οὐκέτι` (`לא` en
#11) ; 1 Esd 8:59 `להביא` ↔ `{..^εἰσήνεγκαν}` / `{...}` ↔ `εἰσήνεγκαν`
(transposition) ; Isa 35:3 #6 `אמצו` ↔ `{...} [4]` (verset LXX suivant →
non aligné).

**Raison :** SimAlign aligne le verset entier ; environ 70 % des `{...X}`
renvoient au même verset, où l'aligneur peut trouver le lien. *Possible* est
neutre pour l'AER : compté juste s'il est trouvé, sans pénalité s'il manque.
Hors du verset, l'aligneur ne peut pas voir l'équivalent : non aligné.
**Écarté :** option A, tout en non aligné (pénaliserait des liens justes dans
le même verset).
**Reste à préciser :** le rattachement des `{...}` vides (sans contenu) à
leur unité source, quand le renvoi n'est pas explicite. Une grande partie est
résolue par les transpositions `{..^X}` (entrée suivante).

## 2026-11-09 — `^` : transpositions, association conservée, doublet supprimé

**Statut : décidé**

`^` n'est pas dans la liste des symboles CATSS. D'après les données, il joue le
rôle de `~` (différence d'ordre) et `^^^` celui de `~~~` (équivalent ailleurs,
transposition) : probablement un changement de caractère à la conversion
(`~~~` : 0 occurrence ; `~` : 18 seulement). **Hypothèse déduite des données,
pas de la documentation CATSS.**

Chiffres : `^` dans 4 124 unités côté hébreu, 7 342 côté grec. Trois emplois :

**1. `X ^ δὲ` — particule postpositive (≈ 2 800 unités grecques).** Le mot
après `^` : `δὲ` 2 458, `δέ` 60, `γὰρ` 57, `οὖν` 38, articles (`ἡ` 56,
`τὸ` 47…). Ex. Gn 4:25 `וידע` ↔ `ἔγνω ^ δὲ` ; Gn 7:19 `והמים` ↔ `τὸ ^ δὲ ὕδωρ`.
Le `ו` initial est rendu par une particule obligatoirement en 2e position.
→ `^` retiré, le bloc reste inchangé.

**2. `{..^X}` + `{...}` ↔ `X` — mot grec transposé (2 820 unités grecques).**
→ l'association est conservée dans l'unité qui porte `{..^X}`, le doublet est
supprimé :

```
Exod 9:32
 5  כי      | {..^γὰρ}    →   כי | γὰρ
 7  {...}   | γὰρ         →   (unité supprimée)
```

**3. `^^^ ^ =X` … `^ X` ↔ `^^^` — mot hébreu transposé (864 paires).**
Même règle : une seule unité, `X` ↔ grec ; l'autre supprimée. L'unité gardée est
celle de la position hébraïque (`^ X`), pour que l'ordre des unités suive le
TM comme dans le cas 2.

```
1 R 15:4
 5  ^^^ ^ =לו   | αὐτῷ    →   (unité supprimée)
 8  ^ לו        | ^^^     →   לו | αὐτῷ
```

Ce traitement se fait **avant** la suppression de la colonne b : sinon l'unité 5
perdrait son hébreu (`=לו` est en colonne b) et l'unité 8 n'aurait pas de grec,
soit 864 faux plus et 864 faux minus.

Les liens issus des transpositions sont **sure** : CATSS donne explicitement
l'équivalent, simplement déplacé, dans le même verset.

**Raison :** une transposition n'est ni un plus ni un minus ; le gold doit
contenir le lien, une seule fois.
**Écartés :** traiter les deux unités comme non alignées (faux plus/minus) ;
garder les deux unités (lien en double).
**Conséquence pour la projection sur CenterBLC :** l'unité gardée n'est plus à
la position grecque du mot. Le gold propre garde la position d'origine
(champ `gr_from` : numéro de l'unité où le grec se trouvait) pour que la
projection des tokens grecs suive l'ordre du texte grec.
**À vérifier :** `{..^X}` côté hébreu (218 unités) — vraisemblablement la même
règle, en miroir ; `X^X` collé dans un mot hébreu (164) ; `^` en colonne b
(`<q2^>`, `<16.1^>`) disparaît avec elle. **Ben Sira** a un balisage propre
(numéros des manuscrits hébreux, ex. Sir 37:4 `מנגד 1 מנוב 5 …`) : règle
spécifique à prévoir.

## 2026-11-09 — Évaluation par blocs CATSS

**Statut : décidé**

**Principe :** un lien prédit est juste s'il reste à l'intérieur d'un bloc
(unité) CATSS. On n'exige pas de lien précis à l'intérieur du bloc, puisque
CATSS ne le donne pas.

Chiffres (`data/gold_clean`, en mots graphiques CATSS) : 302 402 unités
alignées, dont 1↔1 : 142 728 (47,2 %), 1↔n : 134 236 (44,4 %, ex. `בראשׁית` ↔
`ἐν ἀρχῇ`), n↔m : 16 190 (5,4 %, ex. `את האור` ↔ `τὸ φῶς`), n↔1 : 9 248
(3,1 %, ex. `על פני` ↔ `ἐπάνω`) ; plus 27 587 plus et 17 977 minus. Avec la
tokenisation BHSA (proclitiques séparés), la plupart des 1↔n deviennent n↔m.

**Exemple (Gn 1:4)** — blocs A `ו ירא` ↔ `καὶ εἶδεν`, B `אלהים` ↔ `ὁ θεὸς`,
C `את ה אור` ↔ `τὸ φῶς`. Liens prédits : `ירא–εἶδεν` ✓, `אלהים–θεὸς` ✓,
`אור–φῶς` ✓, `את–θεὸς` ✗ (bloc C → bloc B). Précision 3/4 ; rappel par bloc
3/3. `את` non relié et `ה–τὸ` absent ne sont pas pénalisés.

**Écartés :**
- tous les couples d'un bloc en *sure* : exigerait `את ↔ φῶς`, pénaliserait
  un aligneur juste ;
- *sure* = unités 1↔1 seulement : échantillon biaisé (mots pleins sans
  préfixe, les cas faciles) ; gardé seulement comme mesure secondaire ;
- redécouper les blocs (à la main ou par heuristique) : fabriquerait un gold
  que CATSS n'a pas produit.

### Algorithme (`evaluate.py`)

**Entrées**
- textes exportés `data/he/`, `data/lxx/` : par verset, couches `w` (tokens) et
  `g` (numéro de mot graphique de chaque token) ;
- gold propre `data/gold_clean/` : unités avec `ref_mt`, `ref_lxx`, `hb`, `gr`,
  `type` (`align` / `plus` / `minus`), `kind`, `gr_from`, `flags`, et les liens
  reconstruits (`{...}` → *possible*) ;
- sortie de l'aligneur (JSONL) : par verset, `src`, `tgt`, et les liens
  `i-j` pour chaque méthode (`mwmf`, `inter`, `itermax`).

**Étape 1 — Rattacher chaque token à son bloc (projection).** Pour chaque
verset :
1. Hébreu : parcourir les unités du verset dans l'ordre du TM ; découper leur
   `hb` en mots graphiques ; les apparier, dans l'ordre, aux mots graphiques
   BHSA du verset (couche `g`) en comparant les squelettes consonantiques
   (sans points, accents ni distinction shin/sin). Chaque token BHSA reçoit le
   numéro de l'unité de son mot graphique.
2. Grec : parcourir les unités par `ref_lxx`, dans l'ordre du texte grec (en
   tenant compte de `gr_from` pour les transpositions) ; apparier, dans
   l'ordre, leurs mots aux tokens LXX, après normalisation (minuscules, sans
   accents ni ponctuation). Chaque token LXX reçoit le numéro de son unité.
3. Un token non apparié reçoit « inconnu ». Compter et rapporter la
   **couverture** (part de tokens rattachés), par livre : si elle est basse, un
   mauvais score peut venir de la projection et non de l'aligneur.

**Étape 2 — Juger chaque lien prédit `(i, j)`.**
1. Si le token hébreu `i` ou le token grec `j` est « inconnu » : lien ignoré
   (compté à part).
2. Sinon, le lien est **juste** si les deux tokens appartiennent à la même
   unité de type `align`, ou si le couple de leurs unités est un lien
   reconstruit (`{...}`).
3. Sinon il est **faux**. (Un lien qui touche un plus ou un minus est donc
   toujours faux : ces unités n'ont de tokens que d'un côté.)

**Étape 3 — Calculer les mesures.**
1. **Précision** = liens justes / (liens justes + liens faux).
2. **Rappel par bloc** = unités `align` ayant au moins un lien juste à
   l'intérieur / unités `align` dont au moins un token hébreu et un token grec
   sont rattachés.
3. **F1** = moyenne harmonique de la précision et du rappel par bloc.
4. **Exactitude des non-alignements** = tokens des unités `plus` / `minus`
   touchés par aucun lien / tous les tokens rattachés à ces unités.
5. *(Complément)* **Rappel des mots pleins** = tokens hébreux de catégorie
   nom, verbe, adjectif, dans une unité `align`, qui ont au moins un lien vers
   un token grec de la même unité / tous ces tokens. Nécessite la partie du
   discours BHSA (`sp`) dans l'export (couche `m`, pas encore faite).
6. *(Comparaison avec Yousef et al. 2022)* Précision / rappel / AER d'Och &
   Ney avec P = tous les couples de tokens de chaque unité `align` + liens
   reconstruits, S = unités qui restent 1↔1 après tokenisation. Indicatif :
   S est biaisé.

**Étape 4 — Agréger et sortir.** Additionner les comptes (moyenne
micro, pas moyenne des versets), puis calculer les mesures : globalement, par
livre et par méthode (`mwmf`, `inter`, `itermax`). Optionnel : par indicateur
(`{t}`, `{d}`, `{p}`…). Sortie : un tableau (CSV/JSON) avec les comptes bruts
à côté des pourcentages.

**Cas limites :**
- verset où `ref_mt` ≠ `ref_lxx` pour une partie des unités : une unité dont le
  grec est dans un autre verset LXX que celui donné à l'aligneur est hors de
  portée. Elle est comptée à part, pas comme non trouvée ;
- verset sans gold ou sans texte d'un côté : ignoré et listé.

## 2026-11-09 — Expériences configurées par YAML

**Statut : décidé**

Une expérience = un fichier YAML (`config.yaml`) qui fixe toutes les options :
passages (livre, chapitre), couche alignée (`w` / `l`), accents grecs, modèle,
couche du modèle, méthodes. Une seule commande, `python src/run.py config.yaml`,
aligne, évalue et écrit dans `results/<name>/` les alignements, les scores et une
copie de la configuration.

**Raison :** les options en ligne de commande se multipliaient ; chaque résultat
doit pouvoir être reproduit à l'identique (la config est copiée avec lui).

**Premier résultat** (mBERT, couche 8, formes, grec sans accents ; Gen 1, Gen 3,
1 Sam 9) : argmax précision 73,0 %, rappel par bloc 57,4 % ; itermax 64,2 % /
67,4 %. Sans accents est meilleur qu'avec sur les trois chapitres (argmax,
précision : Gen 1 75,1 → 77,8 ; Gen 3 69,7 → 70,7 ; 1 Sam 9 60,9 → 69,5) ;
les lemmes sont moins bons que les formes (Gen 3 : 69,7 → 51,8).

## 2026-11-13 — Expérience de segmentation : mots graphiques vs mots BHSA

**Statut : décidé** (à implémenter, puis à lancer)

Ajouter une troisième valeur pour `tokens` dans `config.yaml` : `tokens: g`.
L'aligneur reçoit alors l'hébreu en **mots graphiques** (`בְּרֵאשִׁ֖ית`) au lieu
des mots BHSA à proclitiques séparés (`בְּ רֵאשִׁ֖ית`).

**Construction :** les tokens de `w` qui ont le même numéro dans `g` sont
recollés sans espace (Gn 1:2 : `וְ הָ אָ֗רֶץ` → `וְהָאָ֗רֶץ`). Les règles de
l'export restent valables : le maqqef sépare deux mots graphiques (`עַל פְּנֵ֣י`
= 2 mots, comme dans CATSS), les noms propres composés restent un seul token
(`בית_אל`), le qere est gardé, l'article caché n'apparaît pas.

Chiffres : sur toute la BHSA exportée, 420 141 tokens `w` contre 304 800 mots
graphiques, soit 27,5 % de tokens en moins.

**Évaluation :** inchangée (évaluation par blocs). Chaque mot graphique se
rattache directement à son unité CATSS, qui est organisée par mots graphiques.
Les liens fins internes au mot (`ב ↔ ἐν`) disparaissent, mais l'évaluation par
blocs ne les récompense pas : les deux segmentations restent comparables.

**Raison :**
- les modèles par embeddings (mBERT, Glot500, XLM-R) ont appris l'hébreu sur
  des textes à préfixes collés (hébreu moderne) ; un `ב` ou `ו` isolé est
  inhabituel pour eux ;
- leur tokenizer redécoupe de toute façon en sous-mots, et SimAlign regroupe
  ensuite par mot : le découpage BHSA n'est peut-être pas nécessaire ;
- l'ancien article (Robert-Hayek, D'Amico, Rey) séparait les proclitiques sans
  comparer avec l'autre option : cette expérience mesure l'effet de la
  segmentation.

**Protocole :** même modèle, même couche, mêmes méthodes, mêmes passages ;
seule `tokens` change (`w` vs `g`). À faire d'abord avec Glot500 (meilleur
résultat actuel, `results/glot500/` : précision 0,83, rappel par blocs 0,71 sur
Gn 1 + Gn 3, méthode `inter`), puis avec mBERT.

**Pas concerné :** le LLM (Gemma) voit déjà le texte pointé complet ; seule la
couche des tokens reliés changerait.

## 2026-11-13 — Option `hebrew_vocalization` : hébreu avec ou sans voyelles

**Statut : décidé** (à mesurer avec l'expérience de segmentation)

Nouvelle option du YAML, `hebrew_vocalization: true / false` (défaut `false`,
le comportement de toutes les expériences précédentes). Elle règle ce que
l'aligneur à embeddings (SimAlign) reçoit côté hébreu :
- `false` : texte consonantique (`בְּרֵאשִׁ֖ית` → `בראשית`) ;
- `true` : vocalisation gardée — voyelles, dagesh / mappiq, points du shin et
  du sin (`בְּרֵאשִׁית`).

Dans les deux cas sont retirés : les accents de cantillation (teʿamim), le
meteg (`וַֽיְהִי` → `וַיְהִי`), la ponctuation (maqqef, paseq, sof pasuq).

**Raison :** les modèles ont appris l'hébreu moderne, écrit sans voyelles ;
mais les voyelles lèvent des ambiguïtés que le texte consonantique laisse (ex.
article et préposition : `בַּ` / `בְּ`), utiles une fois les proclitiques
recollés en mots graphiques. Seule l'expérience peut trancher.
**Choix :** teʿamim toujours retirés : ils notent la cantillation et la
structure du verset, pas le sens des mots, et sont absents des données
d'entraînement des modèles. Une option séparée pourra les tester plus tard
(TODO.md distingue vocalisation et teʿamim).
**Pas concerné :** le LLM, qui voit toujours le texte pointé complet.

**Expériences** (Glot500, mêmes passages et réglages que
`glot500_formes_sans_accents`, seules `tokens` et `hebrew_vocalization`
changent) : `glot500_formes_vocalise_sans_accents` (w, voyelles),
`glot500_mots_graphiques_sans_accents` (g, sans voyelles),
`glot500_mots_graphiques_vocalise_sans_accents` (g, voyelles).

## 2026-11-13 — Restructuration du code en classes (avant `tokens: g`)

**Statut : fait** (2026-11-13, en 4 étapes : `Config` + `Corpus`/`Verse` ;
`Aligner` ; `Gold` + `Evaluator` ; `Experiment`). Non-régression vérifiée à
chaque étape : rejeu identique pour les 4 expériences de référence (liens,
scores, CSV de relecture), relance identique octet par octet pour les 3
expériences SimAlign.

**État actuel :** ~900 lignes dans `src/`, presque uniquement des fonctions, une
seule classe (`OllamaAligner`). Symptômes :
- la lecture des couches d'un verset est faite à trois endroits, de trois façons
  (`align.load`, `evaluate.load_tokens`, `llm_align.graphic_words`) ;
- pas d'interface commune aux aligneurs : `run.py` traite SimAlign et le LLM
  différemment.

**Découpage :**

| Classe | Rôle |
|---|---|
| `Verse` / `Corpus` | charger `data/he`, `data/lxx` ; donner les tokens d'un verset selon la couche (`w`, `l`, `g`) — un seul endroit pour les couches |
| `Aligner` (interface) → `SimAlignAligner`, `OllamaAligner` | `align(verset hébreu, verset grec) → liens` ; le modèle se choisit par la config ; les améliorations (lexique, syntaxe) s'ajoutent comme nouveaux aligneurs ou couches autour d'un aligneur |
| `Gold` | unités CATSS par verset ; rattachement des tokens aux blocs |
| `Evaluator` | juger les liens, calculer les mesures (algorithme de l'entrée « Évaluation par blocs CATSS ») |
| `Config` | lire et vérifier `config.yaml` au démarrage |

**Restent en fonctions :** `normalize.py` (fonctions pures), `gold_clean.py`
(chaîne de transformations lancée une fois), `show.py` (petit script).

**Test de non-régression (obligatoire) :** avant la restructuration, garder les
résultats actuels. Après, relancer les mêmes configs : `scores.csv` doit être
**identique**. La restructuration ne doit changer aucun chiffre.

*Mise en place (2026-11-13).* Expériences de référence dans `experiments/`
(Gen 1, Gen 3, 1 Sam 9 ; formes, grec sans accents) : `mbert_…`, `xlmr_…`,
`glot500_formes_sans_accents` (SimAlign, méthodes `mai`) et
`gemma4_texte_gen3` (LLM, sans réflexion). Résultats relancés avec le code
d'avant la restructuration et copiés dans `tests/reference/`. Contrôle :
`python tests/check_non_regression.py`, en deux volets :
- **rejeu** : les JSONL de référence sont réévalués avec le code actuel (et,
  pour le LLM, ses tableaux reconvertis en liens) ; liens et scores identiques ;
- **relance** (SimAlign seulement) : `results/<nom>/` relancé doit être
  identique à la référence, octet par octet. Vérifié pour mBERT : deux
  exécutions donnent exactement les mêmes fichiers.

*Constat : le LLM n'est pas déterministe*, même à température 0 avec une graine
fixe. Deux exécutions de `gemma4_texte_gen3` diffèrent (Gn 3:6 : `ἰδεῖν`
rattaché ou non à `לעינים`) ; précision 94,1 / 94,3 %, rappel 94,4 / 93,8 %.
D'où le rejeu pour le LLM. Conséquence pour l'article : les scores du LLM
doivent être donnés sur plusieurs exécutions (moyenne et écart).

*Corrections d'étiquetage :* l'ancien `results/mbert_formes_sans_accents/`
contenait des résultats XLM-R (config modifiée sans changer `name`) ;
l'ancien `results/gemma4_12b_texte_gen3/` (« avec réflexion ») est invalide :
JSONL vide, exécution avec réflexion interrompue, scores d'une exécution
antérieure sans réflexion. Aucun résultat avec réflexion n'existe à ce jour.

Résultats de référence (TOTAL des trois chapitres, méthode `inter` ; LLM sur
Gen 3 seulement) :

| Aligneur | Précision | Rappel blocs | Non-al. |
|---|---|---|---|
| mBERT | 73,0 % | 57,4 % | 75,0 % |
| XLM-R | 62,2 % | 44,2 % | 80,9 % |
| Glot500 | **82,8 %** | 69,4 % | **87,5 %** |
| Gemma 4 12B (LLM, Gen 3) | **94,1 %** | **94,4 %** | 22,7 % |

**Ordre :** 1. restructuration + non-régression ; 2. `tokens: g` (implémenté
une seule fois, dans `Verse`).
**Raison de l'ordre :** `tokens: g` touche justement la lecture des couches
éparpillée ; et on sépare un changement qui ne doit pas modifier les scores
(restructuration) d'un changement qui doit les modifier (segmentation). Si un
chiffre bouge, on sait pourquoi.
**Raison des classes :** la partie II (XLM-R, lexique, syntaxe) va multiplier
les aligneurs ; avec l'interface `Aligner`, chaque amélioration est une classe
branchée par la config, sans cas particulier dans `run.py`.
**Écarté :** tout mettre en classes (y compris `normalize`, `gold_clean`) :
pas d'état ni de variantes, une classe n'apporterait que de la cérémonie.

## Architecture cible

```
gold brut ──► gold_clean.py ──► data/gold_clean/ ──► Gold
                                                      │
textes he/lxx ──► Corpus / Verse ──► Aligner ──► JSONL ┤
                  (couches t w l g)  (SimAlign, LLM)    ▼
                                                  Evaluator → scores, CSV
                  Config (YAML) ──► Experiment : enchaîne le tout
```

---

## À trancher

(rien pour l'instant)
