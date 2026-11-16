"""Évaluation de la segmentation de l'hébreu (segment.py), avec BHSA comme référence.

Voir DECISIONS.md « Segmentation de l'hébreu saisi, pour l'app de test » :
- référence : couche w de l'export (mots BHSA), en texte consonantique ; un mot
  graphique = les tokens w de même numéro g ;
- la table est construite sur les chapitres pairs ; les deux méthodes sont
  évaluées sur les chapitres impairs ; Chroniques exclues ;
- mesures : justesse par mot graphique (découpé exactement comme BHSA),
  précision / rappel / F1 des frontières de coupure ; pour tous les mots, les
  formes vues dans les chapitres pairs et les formes non vues ;
- noms composés (בית_אל, un token w pour deux mots graphiques) : gardés dans
  la phrase donnée à dictabert-seg, non évalués ;
- méthodes : table, dictabert-seg, et leur combinaison (CombinedSegmenter :
  table pour les formes vues dans les chapitres pairs, dictabert-seg sinon).

Lancer (depuis la racine du projet) :
    python -m polyglot_align.evaluation.segmentation      -> results/segmentation/
"""
import csv
import json
import logging
from collections import Counter
from pathlib import Path

from polyglot_align.segment import CombinedSegmenter, DictaSegmenter, TableSegmenter, bhsa_words
from polyglot_align.store import DataStore

# nom fixe : lancé avec python -m, __name__ vaut __main__ (hors du journal polyglot_align)
log = logging.getLogger("polyglot_align.evaluation.segmentation")

EXCLUDED_BOOKS = {"1Chr", "2Chr"}


def is_train(chapter: str) -> bool:
    """Chapitres pairs : construction de la table ; impairs : évaluation."""
    return chapter.isdigit() and int(chapter) % 2 == 0


def cuts(parts) -> set:
    """Positions des coupures dans le mot : ("ו", "ב", "שמים") -> {1, 2}."""
    pos, out = 0, set()
    for p in parts[:-1]:
        pos += len(p)
        out.add(pos)
    return out


def measures(c: Counter) -> dict:
    div = lambda a, b: round(a / b, 4) if b else None
    p, r = div(c["tp"], c["tp"] + c["fp"]), div(c["tp"], c["tp"] + c["fn"])
    return {"mots": c["mots"], "justesse": div(c["justes"], c["mots"]),
            "frontieres_precision": p, "frontieres_rappel": r,
            "frontieres_f1": round(2 * p * r / (p + r), 4) if p and r else None}


def evaluate(store: DataStore, dicta: bool = True, out_dir="results/segmentation") -> dict:
    books = [b for b in store.books("he") if b not in EXCLUDED_BOOKS]
    train, test = [], []          # train : (forme, découpage) ; test : (ref, [(forme, découpage)])
    for b in books:
        for v in store.corpus("he", b).verses.values():
            words = bhsa_words(v)
            if is_train(v.chapter):
                train += [(w, p) for w, p in words if p]
            else:
                test.append((v.ref, words))
    table = TableSegmenter().fit(train)
    n_test = sum(1 for _, ws in test for _, p in ws if p)
    log.info("livres : %d (sans les Chroniques) ; table : %d mots graphiques des chapitres pairs, "
             "%d formes ; évaluation : %d mots graphiques des chapitres impairs",
             len(books), len(train), len(table.table), n_test)

    segmenters = {"table": lambda sents: [table.segment_words(s) for s in sents]}
    if dicta:
        model = DictaSegmenter()
        segmenters["dictabert-seg"] = model.segment_sentences
        segmenters["table+dictabert-seg"] = CombinedSegmenter(table, model).segment_sentences

    sentences = [[w for w, _ in ws] for _, ws in test]
    results, errors = {}, []
    for name, run in segmenters.items():
        log.info("%s : segmentation de %d versets…", name, len(sentences))
        preds = run(sentences)
        counts = {k: Counter() for k in ("tous", "vus", "non_vus")}
        patterns = Counter()
        for (ref, ws), pred in zip(test, preds):
            for (word, gold), parts in zip(ws, pred):
                if gold is None:
                    continue
                seen = word in table.table
                ok = tuple(parts) == gold
                g, p = cuts(gold), cuts(parts)
                for k in ("tous", "vus" if seen else "non_vus"):
                    c = counts[k]
                    c["mots"] += 1
                    c["justes"] += ok
                    c["tp"] += len(g & p)
                    c["fp"] += len(p - g)
                    c["fn"] += len(g - p)
                if not ok:
                    patterns[(" ".join(gold), " ".join(parts))] += 1
                    errors.append([name, ref, word, " ".join(gold), " ".join(parts),
                                   "vu" if seen else "non vu"])
        results[name] = {k: measures(c) for k, c in counts.items()}
        results[name]["erreurs_frequentes"] = [
            {"attendu": a, "predit": b, "n": n} for (a, b), n in patterns.most_common(30)]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "erreurs.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["methode", "ref", "mot", "attendu_bhsa", "predit", "forme"])
        w.writerows(errors)
    log.info("\n%-14s %-8s %8s %9s %10s %9s %7s", "méthode", "formes", "mots", "justesse",
             "front. P", "front. R", "F1")
    for name, res in results.items():
        for k in ("tous", "vus", "non_vus"):
            m = res[k]
            pct = lambda v: f"{v:.2%}" if v is not None else "—"
            log.info("%-14s %-8s %8d %9s %10s %9s %7s", name, k, m["mots"], pct(m["justesse"]),
                     pct(m["frontieres_precision"]), pct(m["frontieres_rappel"]), pct(m["frontieres_f1"]))
    log.info("\nRésultats et erreurs dans %s/", out)
    return results


if __name__ == "__main__":
    from polyglot_align.cli import setup_logging
    setup_logging()
    evaluate(DataStore("data"))
