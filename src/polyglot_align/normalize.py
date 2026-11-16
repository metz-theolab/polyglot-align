"""Normalisation des tokens et comparaison de textes, fonctions pures.

Deux familles :
- norm_heb, norm_grc : texte donné aux aligneurs. Les tokens arrivent déjà
  découpés par l'export (couches w, l…). On ne fait que nettoyer chaque
  token : on n'en ajoute ni n'en retire jamais, pour que les indices restent
  ceux de l'export (et donc reliables au gold par la couche g) ;
- heb_letters, grc_letters, project : squelettes de comparaison (lettres
  seules) et rattachement de tokens à des morceaux de texte, lettre par
  lettre. Servent à rattacher les tokens aux unités du gold (evaluation.gold)
  et aux lignes du tableau du LLM (aligners.llm).
"""
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

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


# --- Squelettes de comparaison -----------------------------------------------


def heb_letters(text: str) -> str:
    """Lettres hébraïques seules (sans points, accents, shin/sin), finales = non finales."""
    text = text.translate(str.maketrans("ךםןףץ", "כמנפצ"))
    return re.sub(r"[^א-ת]", "", text)


def grc_letters(text: str) -> str:
    """Lettres grecques seules, sans accents, minuscules, σ = ς."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("ς", "σ")
    return re.sub(r"[^α-ω]", "", text)


def project(tokens: list, pieces: list, letters) -> list:
    """Apparie, dans l'ordre et lettre par lettre, des tokens à des morceaux de
    texte. pieces = [(id, texte)], dans l'ordre. Renvoie, pour chaque token,
    l'id de la majorité de ses lettres (None si aucune lettre appariée).
    Sert à rattacher les tokens aux unités du gold, et les tokens aux lignes
    du tableau du LLM."""
    a, a_tok = [], []
    for i, t in enumerate(tokens):
        for c in letters(t):
            a.append(c)
            a_tok.append(i)
    b, b_unit = [], []
    for uid, text in pieces:
        for c in letters(text):
            b.append(c)
            b_unit.append(uid)
    votes = [Counter() for _ in tokens]
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            votes[a_tok[blk.a + k]][b_unit[blk.b + k]] += 1
    return [v.most_common(1)[0][0] if v else None for v in votes]
