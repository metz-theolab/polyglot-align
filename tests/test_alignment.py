"""Tests de polyglot_align.alignment (format JSONL des résultats).

Usage (depuis la racine du projet) : python -m unittest tests/test_alignment.py -v
"""
import tempfile
import unittest
from pathlib import Path

from polyglot_align.alignment import (AlignmentRecord, VerseAlignment, format_links,
                                      parse_links, read_jsonl)
from polyglot_align.corpus import Verse

REFERENCE = Path(__file__).resolve().parent / "reference"


class TestLinks(unittest.TestCase):
    def test_format_trie(self):
        self.assertEqual(format_links({(1, 2), (0, 0)}), "0-0 1-2")
        self.assertEqual(format_links([]), "")

    def test_parse(self):
        self.assertEqual(parse_links("0-0 2-1"), [(0, 0), (2, 1)])
        self.assertEqual(parse_links(""), [])

    def test_aller_retour(self):
        raw = "0-0 1-1 1-2 5-3"
        self.assertEqual(format_links(parse_links(raw)), raw)


class TestRecord(unittest.TestCase):
    def test_ref_lxx_seulement_si_numero_different(self):
        res = VerseAlignment(["a"], ["b"], {"inter": {(0, 0)}})
        hv = Verse("Ps", "23", "1", {})
        same = AlignmentRecord.from_alignment(hv, Verse("Ps", "23", "1", {}), res)
        other = AlignmentRecord.from_alignment(hv, Verse("Ps", "22", "1", {}), res)
        self.assertIsNone(same.ref_lxx)
        self.assertNotIn("ref_lxx", same.to_json())
        self.assertEqual((other.ref_lxx, other.key, other.lxx_key), ("Ps.22.1", "23.1", "22.1"))

    def test_extra_conserve(self):
        rec = AlignmentRecord("Gen.3.1", ["x"], ["y"], {"llm": [(0, 0)]},
                              extra={"llm_table": [{"hebrew": "x", "greek": "y"}]})
        back = AlignmentRecord.from_json(rec.to_json())
        self.assertEqual(back, rec)

    def test_references_relues_et_reecrites_a_l_identique(self):
        """Chaque ligne des JSONL de référence (tests/reference/) : lecture puis
        écriture redonnent exactement la même ligne."""
        n = 0
        for jsonl in sorted(REFERENCE.glob("*/*.jsonl")):
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                self.assertEqual(AlignmentRecord.from_json(line).to_json(), line)
                n += 1
        self.assertGreater(n, 0)

    def test_read_jsonl(self):
        recs = [AlignmentRecord("Gen.1.1", ["a"], ["b"], {"inter": [(0, 0)]}),
                AlignmentRecord("Ps.23.1", ["c"], ["d"], {"inter": []}, ref_lxx="Ps.22.1")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.jsonl"
            path.write_text("".join(r.to_json() + "\n" for r in recs), encoding="utf-8")
            self.assertEqual(list(read_jsonl(path)), recs)


if __name__ == "__main__":
    unittest.main()
