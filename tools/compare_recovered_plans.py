#!/usr/bin/env python3
"""Compare complete permit-condition sections in four 2021/2022 plan histories.

Text differences guide source reading; they do not measure legal stringency.
Source PDFs and Word files remain unchanged. Section locators and hashes make
the comparison repeatable. No map, implementation, or causal claim is made.
"""

from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/breakdown_review/plan_comparison"
PDF = ROOT / "The_Antarctic_Treaty_44th_Meeting_2022.pdf"
PLANS = [
    (113, "litchfield", "ATIP2020_att017_e.docx", 125, 149, 5),
    (119, "davis", "ATIP2020_att020_e.docx", 171, 192, 7),
    (124, "crozier", "ATCM43_att018_e.docx", 219, 238, 9),
    (139, "biscoe", "ATIP2020_att023_e.docx", 346, 367, 14),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sections(text):
    text = re.sub(r"(?m)^\s*\d{1,3}\s*$", "", text.replace("\f", "\n"))
    start = re.search(r"(?m)^7\.\s+Terms and conditions for entry permits", text)
    assert start, "Missing permit section"
    text = text[start.start() :]
    end = re.search(
        r"(?m)^\s*(?:8\.\s+(?:Supporting documentation|References)|References)\s*$",
        text,
    )
    assert end, "Missing end of permit section"
    text = text[: end.start()]
    markers = list(re.finditer(r"(?m)^\s*7\s*\(([ivx]+)\)\s*", text))
    assert [m[1] for m in markers] == [
        "i",
        "ii",
        "iii",
        "iv",
        "v",
        "vi",
        "vii",
        "viii",
        "ix",
        "x",
        "xi",
    ]
    return {
        m[1]: text[
            m.end() : markers[i + 1].start() if i + 1 < len(markers) else len(text)
        ].strip()
        for i, m in enumerate(markers)
    }


def tokens(text):
    # Cosmetic folding only; retain negations, modal verbs, quantities and dates.
    text = text.translate(
        str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-", "\u00ad": ""})
    )
    return re.findall(r"\w+(?:'\w+)?|[^\w\s]", text.lower())


def changes(a, b):
    result = []
    for tag, i, j, k, l in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            result.append(
                {
                    "operation": tag,
                    "before": " ".join(a[i:j]),
                    "after": " ".join(b[k:l]),
                    "before_context": " ".join(a[max(0, i - 12) : min(len(a), j + 12)]),
                    "after_context": " ".join(b[max(0, k - 12) : min(len(b), l + 12)]),
                }
            )
    return result


def main():
    results = []
    for area, name, file, first, last, measure in PLANS:
        original = BASE / "raw" / file
        assert original.read_bytes().startswith(b"PK"), f"Not a Word document: {file}"
        proposed = subprocess.check_output(
            ["pandoc", str(original), "--track-changes=accept", "-t", "plain"],
            text=True,
        )
        adopted = subprocess.check_output(
            ["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(PDF), "-"],
            text=True,
        )
        assert str(area) in proposed[:150] and str(area) in adopted[:150]
        (BASE / "text" / f"{name}_2021.txt").write_text(proposed)
        (BASE / "text" / f"{name}_2022_adopted.txt").write_text(adopted)
        a, b = sections(proposed), sections(adopted)
        results.append(
            {
                "aspa": area,
                "name": name,
                "draft_file": file,
                "draft_sha256": digest(original),
                "draft_url": f"https://documents.ats.aq/{'ATCM43' if area == 124 else 'ATIP2020'}/att/{file}",
                "measure": f"{measure} (2022)",
                "adopted_pdf_pages": [first, last],
                "permit_sections": [
                    {
                        "section": f"7({key})",
                        "proposed": a[key],
                        "adopted": b[key],
                        "changes": changes(tokens(a[key]), tokens(b[key])),
                    }
                    for key in a
                ],
            }
        )
    output = {
        "checked": "2026-09-07",
        "scope": "All eleven permit-condition subsections for each of the four 2021 non-agreed revisions adopted in 2022. Text comparisons are not classifications of legal stringency. Maps and implementation are outside this comparison.",
        "adopted_source": str(PDF.relative_to(ROOT)),
        "adopted_sha256": digest(PDF),
        "plans": results,
    }
    (BASE / "permit_text_comparison.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    for plan in results:
        print(f"ASPA {plan['aspa']}")
        for section in plan["permit_sections"]:
            print(section["section"], len(section["changes"]), "text differences")
            for change in section["changes"]:
                print("  BEFORE:", change["before_context"])
                print("  AFTER: ", change["after_context"])


if __name__ == "__main__":
    main()
