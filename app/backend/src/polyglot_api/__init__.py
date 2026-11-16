"""polyglot_api : API REST de l'app de test de polyglot-align.

Couche mince au-dessus de la bibliothèque polyglot_align (TextAligner) :
voir decisions-app.md, « Architecture du backend ».

    main.py              create_app(), main() (commande polyglot-api)
    settings.py          réglages (variables d'environnement POLYGLOT_…)
    schemas.py           modèles des requêtes et réponses
    services/aligner.py  AlignerService : chargement unique, un alignement à la fois
    routes/              /api/v1/health, /info, /align, /align/batch, /segment
"""
__version__ = "0.1.0"
