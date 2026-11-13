# Liste des choses à faire et des décisions à prendre ou des points à tester et évaluer



1. Décider du format des données d'entrées
a. Tockenisation
    i. Séparation des préposition + article?
    ii. Séparation des pronom suffixes?
b. Vocaliation et Téamim
    i. suppression de la vocalisation
    ii. suppression de la vocalisation

Il faut un fichier YAML de configuration ou l'on peut gérer l'ensemble de ces options.




2. Texter mBERT, XML-R, Glot500m

3. Ajouter un dictionnaire d'équivalence hébreu / grec et pondérer avec le dictionnaire

4. Fine Tuner à partir de CATSS

5. Doubles textes de Rahlfs : faire DEUX alignements
    - Juges : Judg (texte B) ET JudgA (texte A) contre Judg de BHSA
    - Josué : Josh (B) ET JoshA (A, seulement Jos 15:21-62, 18:21-28, 19:1-45) contre Josh de BHSA
    - à l'évaluation : Judg ↔ gold JudgB, JudgA ↔ gold JudgA, Josh ↔ gold JoshB, JoshA ↔ gold JoshA
    - vérifier le découpage des versets de JoshA (CenterBLC ≠ CATSS ? ex. Jos 15:21)