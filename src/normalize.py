"""Normalisation des tokens avant alignement, partagée par align.py et l'évaluation.

Les tokens arrivent déjà découpés par l'export (couches w, l…). On ne fait que
nettoyer chaque token : on n'en ajoute ni n'en retire jamais, pour que les
indices restent ceux de l'export (et donc reliables au gold par la couche g).
"""
import re
import unicodedata

HEB_MARKS = re.compile(r"[֑-ׇ]")  # voyelles, accents, points shin/sin, ponctuation


def norm_heb(token: str) -> str:
    """Hébreu : texte consonantique (mBERT a appris l'hébreu moderne, non pointé).
    Nom propre composé (בית_אל) : l'espace le garde comme un seul mot pour SimAlign."""
    token = HEB_MARKS.sub("", unicodedata.normalize("NFC", token))
    return token.replace("_", " ")


def norm_grc(token: str, accents: bool = True) -> str:
    """Grec : forme canonique NFC, accents conservés (mBERT est sensible aux accents).
    accents=False : accents et esprits retirés, minuscules (ἀρχῇ -> αρχη)."""
    if accents:
        return unicodedata.normalize("NFC", token)
    token = unicodedata.normalize("NFD", token.lower())
    return "".join(c for c in token if not unicodedata.combining(c))
