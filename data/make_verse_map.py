"""Table d'équivalence des versets hébreu ↔ LXX, tirée du gold CATSS nettoyé.

Voir DECISIONS.md « Appariement des versets par le gold ». Chaque unité du gold
relie un verset TM (sa clé CATSS) au verset LXX où se trouve son grec
(`ref_lxx`). On forme les groupes de versets reliés entre eux (composantes
connexes) et on ne garde que les groupes 1 verset TM ↔ 1 verset LXX, présents
dans les deux exports. Tous les aligneurs et l'évaluation n'apparient les
versets que par cette table.

Lancer depuis data/ (après gold_clean.py et les exports) :
    python make_verse_map.py
Sortie : verse_map.json
    {"<livre grec>": {"he": "<livre hébreu>",
                      "pairs": [["<ch.vs TM>", "<ch.vs LXX>"], ...],   # ordre du TM
                      "exclus": {"<TM>-<LXX>": nombre de groupes, ...}}}
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

GOLD_DIR, HE_DIR, LXX_DIR = Path("gold_clean"), Path("he"), Path("lxx")
OUT = Path("verse_map.json")


def hebrew_book(lxx_book: str) -> str:
    """Livre hébreu d'un livre grec : JoshA -> Josh, JudgA -> Judg, DanTh -> Dan."""
    for suffix in ("Th", "A"):
        if lxx_book.endswith(suffix) and (HE_DIR / f"{lxx_book.removesuffix(suffix)}.json").exists():
            return lxx_book.removesuffix(suffix)
    return lxx_book


def verse_groups(chapters: dict) -> list:
    """Groupes de versets reliés par les unités du gold : [(versets TM, versets LXX)].
    Un verset TM est relié au verset LXX (ref_lxx) de chaque unité qui a du grec ;
    un verset TM sans grec forme un groupe 1 ↔ 0."""
    edges = defaultdict(set)
    for ch, verses in chapters.items():
        for vs, units in verses.items():
            tm = ("he", f"{ch}.{vs}")
            edges[tm]
            for u in units:
                if u["gr"]:
                    lxx = ("lxx", u["ref_lxx"].split(".", 1)[1])
                    edges[tm].add(lxx)
                    edges[lxx].add(tm)
    groups, seen = [], set()
    for start in edges:
        if start in seen:
            continue
        group, stack = [], [start]
        while stack:
            node = stack.pop()
            if node not in seen:
                seen.add(node)
                group.append(node)
                stack.extend(edges[node])
        groups.append(([k for s, k in group if s == "he"], [k for s, k in group if s == "lxx"]))
    return groups


def book_map(lxx_book: str) -> dict:
    he_book = hebrew_book(lxx_book)
    (chapters,) = json.loads((GOLD_DIR / f"{lxx_book}.json").read_text(encoding="utf-8")).values()
    (he,) = json.loads((HE_DIR / f"{he_book}.json").read_text(encoding="utf-8")).values()
    (lxx,) = json.loads((LXX_DIR / f"{lxx_book}.json").read_text(encoding="utf-8")).values()
    exists = lambda text, key: key.split(".")[1] in text.get(key.split(".")[0], {})
    pairs, excluded = [], Counter()
    for tm, gr in verse_groups(chapters):
        if len(tm) != 1 or len(gr) != 1:
            excluded[f"{len(tm)}-{len(gr)}"] += 1
        elif not (exists(he, tm[0]) and exists(lxx, gr[0])):
            excluded["absent_export"] += 1
        else:
            pairs.append([tm[0], gr[0]])
    order = lambda key: tuple(int(p) if p.isdigit() else 0 for p in key.split("."))
    pairs.sort(key=lambda p: order(p[0]))
    return {"he": he_book, "pairs": pairs, "exclus": dict(sorted(excluded.items()))}


def main() -> None:
    table, skipped = {}, []
    for path in sorted(GOLD_DIR.glob("*.json")):
        book = path.stem
        if book.startswith("_"):
            continue
        if not (LXX_DIR / f"{book}.json").exists() or not (HE_DIR / f"{hebrew_book(book)}.json").exists():
            skipped.append(book)   # pas d'export grec ou hébreu de ce nom (Sir, Ezra/Neh…)
            continue
        table[book] = book_map(book)
    OUT.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")

    kept = sum(len(b["pairs"]) for b in table.values())
    excluded = sum((Counter(b["exclus"]) for b in table.values()), Counter())
    print(f"{OUT} : {len(table)} livres, {kept} paires de versets 1 ↔ 1 gardées")
    print("groupes exclus (versets TM - versets LXX) :", dict(excluded.most_common()))
    print("livres du gold sans table (pas d'export de ce nom) :", ", ".join(skipped))


if __name__ == "__main__":
    sys.exit(main())
