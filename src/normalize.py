"""Normalisation des tokens avant alignement, partagée par align.py et l'évaluation.

Les tokens arrivent déjà découpés par l'export (couches w, l…). On ne fait que
nettoyer chaque token : on n'en ajoute ni n'en retire jamais, pour que les
indices restent ceux de l'export (et donc reliables au gold par la couche g).
"""
import re
import unicodedata

HEB_MARKS = re.compile(r"[֑-ׇ]")  # voyelles, accents, points shin/sin, ponctuation
# Tout sauf la vocalisation : cantillation (teʿamim), meteg, maqqef, paseq, sof pasuq,
# points supra/infra-linéaires, nun inversé. Restent : voyelles (sheva…qubuts, qamats
# qatan), dagesh/mappiq, rafe, points du shin et du sin.
HEB_NON_VOWELS = re.compile(r"[֑-ֽ֯־׀׃ׅׄ׆]")


def norm_heb(token: str, vocalization: bool = False) -> str:
    """Hébreu. vocalization=False : texte consonantique (mBERT a appris l'hébreu
    moderne, non pointé) ; True : voyelles gardées, cantillation retirée.
    Nom propre composé (בית_אל) : l'espace le garde comme un seul mot pour SimAlign."""
    marks = HEB_NON_VOWELS if vocalization else HEB_MARKS
    token = marks.sub("", unicodedata.normalize("NFC", token))
    return token.replace("_", " ")


def norm_grc(token: str, accents: bool = True) -> str:
    """Grec : forme canonique NFC, accents conservés (mBERT est sensible aux accents).
    accents=False : accents et esprits retirés, minuscules (ἀρχῇ -> αρχη)."""
    if accents:
        return unicodedata.normalize("NFC", token)
    token = unicodedata.normalize("NFD", token.lower())
    return "".join(c for c in token if not unicodedata.combining(c))
