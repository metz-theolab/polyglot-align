"""Alignement d'un passage : parcourt les versets et écrit le JSONL (appelé par experiment.py).

Le travail sur chaque verset est fait par un Aligner (aligners/) ; ce module
ne fait qu'écrire les résultats. Les paires de versets viennent de la table
d'appariement (DataStore.verse_pairs) : un verset hébreu n'est aligné qu'avec
son équivalent LXX.

Sortie : JSONL, une ligne par verset (format dans alignment.py), écrite et
vidée sur disque verset par verset. Reprise : si le fichier existe déjà, les
versets qu'il contient ne sont pas réalignés (voir DECISIONS.md, étape 5 de
« Paquet Python installable… »).
"""
import json
import logging
import os
from pathlib import Path

from polyglot_align.alignment import AlignmentRecord

log = logging.getLogger(__name__)


def done_records(path) -> tuple[list, int]:
    """Versets déjà écrits dans le JSONL `path` et longueur (en octets) de la
    partie complète du fichier ; ([], 0) s'il n'existe pas. Une ligne n'est
    complète que suivie de son retour à la ligne : un reste final (arrêt
    pendant l'écriture) est ignoré, le verset sera refait. Une ligne complète
    mais illisible lève ValueError."""
    path = Path(path)
    if not path.exists():
        return [], 0
    data = path.read_bytes()
    *lines, rest = data.split(b"\n")
    if rest:
        log.warning("%s : dernière ligne incomplète ignorée (verset refait)", path)
    records = []
    for n, line in enumerate(lines, 1):
        try:
            records.append(AlignmentRecord.from_json(line.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"{path}, ligne {n} : illisible ({e})") from e
    return records, len(data) - len(rest)


def align(aligner, pairs, out_path) -> tuple[int, int]:
    """Aligne les paires de versets `pairs` [(Verse hébreu, Verse grec)] et
    écrit le JSONL ; les versets déjà présents dans `out_path` sont repris tels
    quels. Renvoie (versets alignés pendant cet appel, versets repris)."""
    done, size = done_records(out_path)
    refs = {hv.ref for hv, _ in pairs}
    stray = [r.ref for r in done if r.ref not in refs]
    if stray:
        raise ValueError(f"{out_path} : versets hors du passage ({', '.join(stray[:3])}…) ; "
                         "relancer avec --force")
    done_refs = {r.ref for r in done}
    if done:
        log.info("  reprise : %d versets déjà alignés sur %d", len(done_refs), len(pairs))
    todo = [(hv, gv) for hv, gv in pairs if hv.ref not in done_refs]
    if Path(out_path).exists():
        os.truncate(out_path, size)       # retire seulement un reste incomplet
    with open(out_path, "a", encoding="utf-8") as out:
        for n, (hv, gv) in enumerate(todo, len(done_refs) + 1):
            log.info("  %s (%d/%d)", hv.ref, n, len(pairs))
            res = aligner.align(hv, gv)
            out.write(AlignmentRecord.from_alignment(hv, gv, res).to_json() + "\n")
            out.flush()
    return len(todo), len(done)
