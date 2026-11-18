"""Export de la Peshitta (Text-Fabric, ETCBC/peshitta) en JSON : un fichier par livre.

Voir DECISIONS.md « Export de la Peshitta ». Format (comme data/he, data/lxx,
sans couche l : le corpus n'a pas de lemmes) :
    {"Gen": {"1": {"1": {
        "t": "ܒܪܫܝܬ ܒܪܐ ܐܠܗܐ …",   texte du verset (mots et ponctuation)
        "w": "ܒܪܫܝܬ ܒܪܐ ܐܠܗܐ …",   un token par mot Text-Fabric (= mot graphique,
                                      enclitiques non séparés)
        "g": "0 1 2 …"              numéro du mot graphique de chaque token
    }}}}
w et g ont le même nombre de tokens ; aucun token ne contient d'espace.

Livres : sigles Peshitta (Gn, Ex…) convertis en abréviations OSIS (Gen, Exod…),
les mêmes que pour la BHSA et la LXX. Livres à deux témoins (sigle suffixé _A
/ _B) : le témoin A garde le nom simple, le témoin B prend le suffixe B. Livres
sans équivalent hébreu : data/syr/non_aligned/.

Écrit aussi data/syr/_rapport.json : livres, versets, mots, livres à deux
témoins, signes diacritiques syriaques (chiffres à reporter dans DECISIONS.md).

Usage (depuis data/) : python export_peshitta_tf.py
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from tf.app import use

CORPUS = "ETCBC/peshitta"
VERSION = "0.2"
OUT_DIR = Path("syr")
NON_ALIGNED_DIR = OUT_DIR / "non_aligned"   # livres sans équivalent hébreu

# Sigles Peshitta des 39 livres de la Bible hébraïque -> abréviations OSIS (comme BHSA / LXX)
HEBREW_BOOKS = {
    "Gn": "Gen", "Ex": "Exod", "Lv": "Lev", "Nm": "Num", "Dt": "Deut",
    "Jos": "Josh", "Jd": "Judg", "Ru": "Ruth", "Sm1": "1Sam", "Sm2": "2Sam",
    "Rg1": "1Kgs", "Rg2": "2Kgs", "Chr1": "1Chr", "Chr2": "2Chr", "Ezr": "Ezra",
    "Neh": "Neh", "Est": "Esth", "Jb": "Job", "Ps": "Ps", "Pr": "Prov",
    "Ec": "Eccl", "Ct": "Song", "Is": "Isa", "Jr": "Jer", "Thr": "Lam",
    "Ez": "Ezek", "Dn": "Dan", "Hs": "Hos", "Jl": "Joel", "Am": "Amos",
    "Ob": "Obad", "Jon": "Jonah", "Mi": "Mic", "Na": "Nah", "Hb": "Hab",
    "Zf": "Zeph", "Hg": "Hag", "Sa": "Zech", "Ml": "Mal",
}
# Livres sans équivalent hébreu : mêmes noms que data/lxx/non_aligned/ quand le
# livre y existe ; un sigle absent de la table garde son nom Peshitta
NON_ALIGNED_BOOKS = {
    "Sap": "Wis", "EpJr": "EpJer", "Bar": "Bar", "BelDr": "Bel", "Sus": "Sus",
    "Jdt": "Jdt", "Sir": "Sir", "Mc1": "1Mac", "Mc2": "2Mac", "Mc3": "3Mac",
    "Mc4": "4Mac", "Oda": "Od", "PsS": "PsSol", "Esr3": "1Esdr", "Tb": "Tob",
    "EpBar": "EpBar", "ApBar": "2Bar", "Esr4": "4Ezra", "OrM": "PrMan", "ApcPs": "AddPs",
}

SYRIAC_LETTERS = re.compile(r"[ܐ-ܯ]")        # lettres syriaques
SYRIAC_DIACRITICS = re.compile(r"[ܰ-݊]")     # voyelles et signes diacritiques

A = use(CORPUS, version=VERSION, silent="deep")
F, L = A.api.F, A.api.L


def book_name(siglum: str) -> tuple:
    """(nom du fichier, aligné ?) : "Gn" -> ("Gen", True) ;
    "Tb_B" -> ("TobB", False) ; témoin A : nom simple."""
    base, _, witness = siglum.partition("_")
    if base in HEBREW_BOOKS:
        name, aligned = HEBREW_BOOKS[base], True
    else:
        name, aligned = NON_ALIGNED_BOOKS.get(base, base), False
    return name + ("B" if witness == "B" else ""), aligned


def export_verse(v, report: Counter) -> dict:
    """Couches d'un verset : t (texte), w (mots), g (numéros de mots graphiques)."""
    words, text = [], []
    for w in L.d(v, otype="word"):
        form = unicodedata.normalize("NFC", F.word.v(w) or "")
        text.append(form + (F.trailer.v(w) or ""))
        if not form.strip():
            report["mots_vides_ignores"] += 1
            continue
        assert not re.search(r"\s", form), f"espace dans un mot : {F.word_etcbc.v(w)}"
        words.append(form)
        report["mots"] += 1
        report["mots_avec_diacritiques"] += bool(SYRIAC_DIACRITICS.search(form))
        for c in form:
            if not SYRIAC_LETTERS.match(c):
                report[f"autre_caractere U+{ord(c):04X} {unicodedata.name(c, '?')}"] += 1
    return {
        "t": " ".join("".join(text).split()),
        "w": " ".join(words),
        "g": " ".join(str(i) for i in range(len(words))),   # un mot TF = un mot graphique
    }


books = defaultdict(lambda: defaultdict(dict))   # nom -> chapitre -> verset -> couches
aligned_names, sigla, report = set(), {}, Counter()
for v in F.otype.s("verse"):
    siglum = F.book.v(L.u(v, otype="book")[0])
    name, aligned = book_name(siglum)
    sigla[name] = siglum
    if aligned:
        aligned_names.add(name)
    ch, vs = str(F.chapter.v(L.u(v, otype="chapter")[0])), str(F.verse.v(v))
    assert vs not in books[name][ch], f"référence en double : {name}.{ch}.{vs} ({siglum})"
    layers = export_verse(v, report)
    if not layers["w"]:
        report["versets_vides_ignores"] += 1
        continue
    books[name][ch][vs] = layers
    report["versets"] += 1

NON_ALIGNED_DIR.mkdir(parents=True, exist_ok=True)
for name, chapters in books.items():
    path = (OUT_DIR if name in aligned_names else NON_ALIGNED_DIR) / f"{name}.json"
    path.write_text(json.dumps({name: chapters}, ensure_ascii=False, indent=1), encoding="utf-8")

missing = sorted(set(HEBREW_BOOKS.values()) - aligned_names)
summary = {
    "corpus": f"{CORPUS} {VERSION}",
    "livres_alignables": sorted(aligned_names),
    "livres_hebreux_absents": missing,
    "livres_sans_equivalent_hebreu": sorted(set(books) - aligned_names),
    "livres_a_deux_temoins": sorted(s for s in sigla.values() if "_" in s),
    "sigles": dict(sorted(sigla.items())),
    "comptes": dict(sorted(report.items())),
}
(OUT_DIR / "_rapport.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"{len(aligned_names)} livres alignables dans {OUT_DIR}/, "
      f"{len(books) - len(aligned_names)} sans équivalent hébreu dans {NON_ALIGNED_DIR}/")
print(f"{report['versets']} versets, {report['mots']} mots ; "
      f"mots avec voyelles ou diacritiques : {report['mots_avec_diacritiques']}")
if missing:
    print("ATTENTION : livres hébreux absents de la Peshitta exportée :", ", ".join(missing))
print(f"détail : {OUT_DIR}/_rapport.json")
