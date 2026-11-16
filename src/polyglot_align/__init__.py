"""polyglot_align : alignement mot à mot du texte hébreu et de la Septante,
évalué contre le gold CATSS.

Modules :
    config        Config, Passage : lecture et vérification du YAML d'une expérience
    corpus        Verse, Corpus, VerseMap : textes exportés et appariement des versets
    normalize     normalisation des tokens
    aligners/     Aligner (interface) et une classe par méthode (SimAlign, eflomal, LLM)
    evaluation/   Gold, Evaluator ; gold_clean (préparation du gold)
    experiment    Experiment : alignement, évaluation, écriture de results/<nom>/
    report        tableaux et figures de l'article à partir de results/
    cli           ligne de commande `polyglot-align`
"""
__version__ = "0.1.0"
