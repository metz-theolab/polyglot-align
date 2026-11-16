"""Contrôle de align("texte A", "texte B") (textalign.py) contre le gold CATSS.

Voir DECISIONS.md « align("texte A", "texte B") », Contrôle. Des versets du
corpus, tirés au hasard (graine fixe), sont retirés de la table
d'apprentissage puis passés comme du texte saisi (couche t, hébreu et grec) :
segmentation, ajout à la table, apprentissage d'eflomal, alignement. Les
liens sont évalués contre le gold (Evaluator), comme une expérience, et
comparés à ceux d'une expérience complète (results/<référence>/) sur les
mêmes versets. Seuls les versets dont les tokens ont le même nombre que
l'export sont évalués (Evaluator ; écartés surtout : qere, dont les lettres
diffèrent du texte t, et noms composés), et les deux alignements sont
évalués sur exactement ces versets.

Lancer (depuis la racine du projet) :
    python -m polyglot_align.evaluation.textalign_check
"""
import logging
import random
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from polyglot_align.alignment import AlignmentRecord, read_jsonl
from polyglot_align.evaluation.evaluate import Evaluator, measures
from polyglot_align.store import DataStore
from polyglot_align.textalign import TextAligner

# nom fixe : lancé avec python -m, __name__ vaut __main__ (hors du journal polyglot_align)
log = logging.getLogger("polyglot_align.evaluation.textalign_check")


def score(store, records_by_book: dict) -> dict:
    """{(livre hébreu, livre grec): [AlignmentRecord]} -> mesures par méthode
    (comptes additionnés sur tous les livres) et versets ignorés."""
    counts, skipped = defaultdict(Counter), Counter()
    with tempfile.TemporaryDirectory() as tmp:
        for (he_book, lxx_book), recs in records_by_book.items():
            path = Path(tmp) / f"{lxx_book}.jsonl"
            path.write_text("".join(r.to_json() + "\n" for r in recs), encoding="utf-8")
            res = Evaluator.from_store(store, he_book, lxx_book).evaluate(path)
            skipped.update(res["versets_ignores"])
            for m, r in res["methodes"].items():
                counts[m].update(r["comptes"])
    return {"mesures": {m: measures(c) for m, c in counts.items()},
            "versets": {m: c["versets"] for m, c in counts.items()}, "ignores": dict(skipped)}


def check(n: int = 300, seed: int = 0, reference: str = "eflomal_unvocalized") -> dict:
    store = DataStore("data")
    aligner = TextAligner(store)
    pairs = list(aligner.table_pairs)
    sample = random.Random(seed).sample(pairs, n)
    chosen = {(hv.ref, gv.ref) for hv, gv in sample}
    # les versets testés ne sont pas dans la table : ils ne sont vus que comme texte saisi
    aligner.table_pairs = [(hv, gv) for hv, gv in pairs if (hv.ref, gv.ref) not in chosen]
    log.info("%d versets tirés au hasard (graine %d), retirés de la table (%d paires restantes)",
             n, seed, len(aligner.table_pairs))
    results = aligner.align_many([(hv.layers["t"], gv.layers["t"]) for hv, gv in sample])

    typed, ref_records = defaultdict(list), defaultdict(list)
    saved, comparable = {}, 0
    for (hv, gv), res in zip(sample, results):
        if (len(res.hebrew.tokens("w")), len(res.greek.tokens("w"))) != (len(hv.tokens("w")),
                                                                         len(gv.tokens("w"))):
            continue    # tokens différents de l'export : non évaluable contre le gold
        comparable += 1
        book = (hv.book, gv.book)
        links = {"inter": res.links["sure"], "gdfa": res.links["all"]}   # noms de l'expérience
        typed[book].append(AlignmentRecord(hv.ref, res.hebrew.tokens("w"), res.greek.tokens("w"),
                                           links, ref_lxx=gv.ref if gv.key != hv.key else None))
        if gv.book not in saved:   # résultats de l'expérience de référence, livre par livre
            saved[gv.book] = {(r.key, r.lxx_key): r
                              for r in read_jsonl(Path("results") / reference / f"{gv.book}.jsonl")}
        ref_records[book].append(saved[gv.book][(hv.key, gv.key)])

    log.info("versets évaluables (mêmes nombres de tokens que l'export) : %d sur %d", comparable, n)
    out = {"saisi": score(store, typed), reference: score(store, ref_records)}
    pct = lambda v: f"{v:.1%}" if v is not None else "—"
    log.info("\n%-22s %-6s %8s %10s %7s %8s %8s", "alignement", "méthode", "versets", "précision",
             "rappel", "F1", "non-al.")
    for name, res in out.items():
        for m in ("inter", "gdfa"):
            x = res["mesures"][m]
            log.info("%-22s %-6s %8d %10s %7s %8s %8s", name, m, res["versets"][m], pct(x["precision"]),
                     pct(x["rappel_blocs"]), pct(x["f1"]), pct(x["nonalign_exactitude"]))
        log.info("%-22s versets ignorés : %s", name, res["ignores"] or "aucun")
    return out


if __name__ == "__main__":
    from polyglot_align.cli import setup_logging
    setup_logging()
    check()
