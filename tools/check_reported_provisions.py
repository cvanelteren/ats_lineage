"""Check source locations for selected report-based provision comparisons.

This checks provenance, anchors and adoption identities, not the interpretation
of a provision or its retention in a complete adopted management plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from tools.check_aspa_cohort import normalise, page_window
except ModuleNotFoundError:
    from check_aspa_cohort import normalise, page_window

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/breakdown_review/reported_provision_changes.json"


def check_case(case: dict, text: str) -> None:
    window = page_window(text, case["pdf_pages"])
    for anchor in case["anchors"]:
        if normalise(anchor) not in window:
            raise ValueError(f"missing source anchor: {case['id']}: {anchor}")
    adoption = page_window(text, case["adoption_pages"])
    if normalise(case["adoption_anchor"]) not in adoption:
        raise ValueError(f"missing adoption anchor: {case['id']}")
    area_name = {"ASPA": "Protected", "ASMA": "Managed"}[case["area_type"]]
    pattern = (
        rf"Measure {case['measure']} \({case['year']}\) "
        rf"Antarctic Specially {area_name} Area No {case['area']}\b"
    )
    if not re.search(pattern, adoption):
        raise ValueError(f"adoption identity mismatch: {case['id']}")
    if case["full_plan_comparison_complete"] or case["legal_effect_checked"]:
        raise ValueError(
            "report-only check cannot certify plan comparison or legal effect"
        )


def build(data_path: Path, pdf_root: Path) -> dict:
    data = json.loads(data_path.read_text())
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case identity")
    if any(value is not None for value in data["population_level_results"].values()):
        raise ValueError(
            "selected report comparisons cannot establish population rates"
        )
    texts, hashes = {}, {}
    for key, source in data["sources"].items():
        pdf = pdf_root / source["file"]
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"source hash mismatch: {key}")
        hashes[key] = digest
        texts[key] = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    for case in data["cases"]:
        check_case(case, texts[case["source"]])
    return {
        "input_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "source_sha256": hashes,
        "cases_checked": ids,
        "checks": "Original PDF hashes, declared page anchors, and year/Measure/area-type/area identities. No independent substantive validation or complete-plan comparison.",
        "population_level_results": data["population_level_results"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument(
        "--pdf-root", type=Path, default=ROOT.parent / "ats_corpus_data/pdfs"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "research/breakdown_review/reported_provision_checks.json",
    )
    args = parser.parse_args()
    result = build(args.data, args.pdf_root)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
