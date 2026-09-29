#!/usr/bin/env python3
"""Check disputed 2021 wording against the four plans adopted in 2022.

Predecessor excerpts are a separate, explicitly web-read source record. This
script verifies local original-file hashes and re-extracts Word/PDF text; it
does not pretend to independently validate the web-only predecessor record.
"""

import json
import re
import subprocess
from pathlib import Path

from compare_recovered_plans import BASE, PDF, PLANS, ROOT, digest


def normalise(text):
    return re.sub(r"\s+", " ", text).strip()


def first_aim(text):
    start = re.search(r"2\.\s+Aims and [Oo]bjectives", text)
    assert start, "Missing aims section"
    match = re.search(r"[Aa]void degradation[^;]+;", text[start.end() :])
    assert match, "Missing first aim"
    return normalise(match[0])


def boundary_section(text):
    start = re.search(r"(?m)^\s*(?:-\s+)?Boundaries\s*$", text)
    assert start, "Missing boundaries subsection"
    end = re.search(r"(?m)^\s*(?:-\s+)?Climate\s*$", text[start.end() :])
    assert end, "Missing next subsection"
    return normalise(text[start.end() : start.end() + end.start()])


def build():
    cache = json.loads((BASE / "permit_text_comparison.json").read_text())
    baseline_path = BASE / "predecessor_clause_sources.json"
    baseline = json.loads(baseline_path.read_text())
    assert digest(PDF) == cache["adopted_sha256"], "Adopted PDF changed"
    prior = {r["aspa"]: r for r in baseline["plans"]}
    old_cache = {r["aspa"]: r for r in cache["plans"]}
    records = []
    for aspa, name, filename, first, last, measure in PLANS:
        original = BASE / "raw" / filename
        assert digest(original) == old_cache[aspa]["draft_sha256"]
        proposed = subprocess.check_output(
            ["pandoc", str(original), "--track-changes=accept", "-t", "plain"],
            text=True,
        )
        adopted = subprocess.check_output(
            ["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(PDF), "-"],
            text=True,
        )
        assert str(aspa) in proposed[:150] and str(aspa) in adopted[:150]
        a, b = first_aim(proposed), first_aim(adopted)
        assert a.lower() == b.lower(), f"First aim changed: ASPA {aspa}"
        assert "preventing unnecessary human presence, disturbance and sampling" in b
        assert "presence" not in prior[aspa]["aim_tail"]
        pages = [
            first + i
            for i, page in enumerate(adopted.split("\f"))
            if "preventing unnecessary human presence" in normalise(page)
        ]
        assert len(pages) == 1
        record = {
            "aspa": aspa,
            "predecessor": prior[aspa],
            "draft_file": str(original.relative_to(ROOT)),
            "draft_sha256": digest(original),
            "draft_url": old_cache[aspa]["draft_url"],
            "adopted_measure": f"{measure} (2022)",
            "adopted_aim_pdf_page": pages[0],
            "proposed_aim": a,
            "adopted_aim": b,
            "proposed_aim_retained": True,
            "presence_added_to_predecessor_aim": True,
            "interpretation": "Retained addition to a management aim; this comparison alone does not establish a new freestanding prohibition on presence.",
        }
        if aspa == 139:
            a_bound, b_bound = boundary_section(proposed), boundary_section(adopted)
            assert a_bound == b_bound, "Biscoe boundary subsection changed"
            for text in [a_bound, b_bound]:
                assert "A recent detailed review" not in text
                assert "current or planned scientific studies" not in text
            explanation = "The marine component is now excluded from the Area because of the lack of information on its values."
            assert explanation in normalise(proposed) and explanation in normalise(
                adopted
            )
            record["boundary"] = {
                "predecessor_source": baseline["biscoe_boundary"],
                "proposed": a_bound,
                "adopted": b_bound,
                "normalised_text_identical": True,
                "historical_rationale_in_section_6i": {
                    "predecessor": True,
                    "proposed": False,
                    "adopted": False,
                },
                "shorter_explanation_retained_in_section_1": True,
                "interpretation": "The disputed removal of the section 6(i) historical rationale persisted. An earlier section retained a shorter explanation. This is not evidence that this revision extended the boundary into the marine area.",
            }
        records.append(record)
    return {
        "checked": "2026-09-28",
        "scope": baseline["scope"],
        "predecessor_record": str(baseline_path.relative_to(ROOT)),
        "predecessor_record_sha256": digest(baseline_path),
        "predecessor_provenance": baseline["provenance"],
        "adopted_source": str(PDF.relative_to(ROOT)),
        "adopted_sha256": digest(PDF),
        "records": records,
        "limits": [
            "Predecessor source excerpts require reader inspection at the cited URLs; no downloaded predecessor-PDF hashes are claimed.",
            "No complete predecessor-to-adopted plan comparison or map comparison.",
            "No independent human adjudication, implementation, compliance or ecological outcome assessment.",
        ],
    }


if __name__ == "__main__":
    result = build()
    target = BASE / "disputed_clause_comparison.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for record in result["records"]:
        print(
            f"ASPA {record['aspa']}: disputed first aim retained; adopted PDF page {record['adopted_aim_pdf_page']}"
        )
    print(
        "Biscoe: section 6(i) rationale remains absent; section 1 explanation remains present."
    )
