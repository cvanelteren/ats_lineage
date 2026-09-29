"""Compare report-defined approval-stage ASPA requests across two five-meeting periods.

Same-meeting dispositions are not final proposal outcomes or independent trials.
Source checks establish provenance and consistency, not substantive retention.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from tools.check_aspa_cohort import normalise, page_window
    from tools.check_aspa_recent_series import (
        adoption_pairs,
        blocked,
        build as check_recent,
        summarize,
        validate_rows,
    )
except ModuleNotFoundError:
    from check_aspa_cohort import normalise, page_window
    from check_aspa_recent_series import (
        adoption_pairs,
        blocked,
        build as check_recent,
        summarize,
        validate_rows,
    )

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/breakdown_review"


def load_earlier(data_root: Path = DATA) -> list[dict]:
    with (data_root / "aspa_2015_2019_approval.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("malformed earlier CSV row")
        for key in ("year", "measure", "wp"):
            row[key] = int(row[key]) if row[key] else None
        row["area_ids"] = [int(v) for v in row["area_ids"].split("|") if v]
        if row["requested_stage"] != "approval":
            raise ValueError("earlier file contains only approval-stage requests")
    validate_rows(rows)
    return rows


def counts(rows: list[dict]) -> dict:
    return {
        "requests_at_meetings": len(rows),
        "adopted": sum(r["atcm_disposition"] == "adopted" for r in rows),
        "recorded_non_agreement": sum(blocked(r) for r in rows),
        "awaiting_external_approval": sum(
            r["atcm_disposition"] == "pending_external_approval" for r in rows
        ),
    }


def comparison(earlier: list[dict], recent: list[dict]) -> dict:
    validate_rows(earlier + recent)
    if any(r["requested_stage"] != "approval" for r in earlier):
        raise ValueError("earlier denominator must contain approval requests only")
    recent_approval = [r for r in recent if r["requested_stage"] == "approval"]
    all_approval = earlier + recent_approval
    annual = summarize(all_approval)["annual"]
    # Earlier records reconstruct only the approval stage. Do not turn omitted
    # stages into reported zeros or call these totals all plan considerations.
    for row in annual:
        for key in (
            "plan_considerations",
            "earlier_stage_referrals",
            "unchanged_reviews",
        ):
            row.pop(key)
    return {
        "annual": annual,
        "earlier_all_approval": counts(earlier),
        "recent_all_approval": counts(recent_approval),
        "earlier_revisions": counts([r for r in earlier if r["kind"] == "revision"]),
        "recent_revisions": counts(
            [r for r in recent_approval if r["kind"] == "revision"]
        ),
        "earlier_revisions_excluding_2018": counts(
            [r for r in earlier if r["kind"] == "revision" and r["year"] != 2018]
        ),
        "unit": "request at a meeting; repeated areas and requests remain dependent",
        "substantive_retention_rate": None,
        "historical_loss_of_capacity": None,
        "interpretation": "Compare recorded same-meeting dispositions, including revision-only counts and exclusion of the shortened 2018 meeting. Content, recording practices, selection into approval and later recovery remain separate questions.",
    }


def forwarded_areas(raw_text: str, pages: list[int]) -> set[int]:
    first, last = pages
    raw_window = "\n".join(raw_text.split("\f")[first - 1 : last])
    # The advice tables print one ASPA per line. Paper-list mentions are prose
    # or bullets, not these table rows. ASMA rows stay outside the population.
    return {int(m[1]) for m in re.finditer(r"^ASPA\s+(\d+)\b", raw_window, re.M)}


def build(data_root: Path, pdf_root: Path) -> dict:
    earlier = load_earlier(data_root)
    meta = json.loads((data_root / "aspa_earlier_sources.json").read_text())
    if {r["year"] for r in earlier} != {int(y) for y in meta["sources"]}:
        raise ValueError("source years and coded years differ")
    checks = []
    for year_string, source in meta["sources"].items():
        year = int(year_string)
        pdf = pdf_root / source["file"]
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"source hash mismatch: {year}")
        text = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        windows = {}
        for key, evidence in source["windows"].items():
            window = page_window(text, evidence["pages"])
            if normalise(evidence["anchor"]) not in window:
                raise ValueError(f"missing source anchor: {year}/{key}")
            windows[key] = window
            checks.append(f"{year}/{key}")
        rows = [r for r in earlier if r["year"] == year]
        coded_areas = {a for r in rows for a in r["area_ids"]}
        if coded_areas & set(source["excluded_areas"]):
            raise ValueError(f"excluded request entered denominator: {year}")
        forwarded = forwarded_areas(text, source["windows"]["revisions"]["pages"])
        if forwarded != coded_areas:
            raise ValueError(
                f"CEP list mismatch {year}: listed={forwarded}, coded={coded_areas}"
            )
        adopted = adoption_pairs(
            windows["adopted"].split("Accepting the CEP’s advice", 1)[-1], year
        )
        coded_pairs = {
            (r["measure"], r["area_ids"][0])
            for r in rows
            if r["atcm_disposition"] == "adopted"
        }
        if adopted != coded_pairs:
            raise ValueError(
                f"ATCM list mismatch {year}: listed={adopted}, coded={coded_pairs}"
            )
    recent = check_recent(data_root, pdf_root)
    return {
        "inputs": {
            name: hashlib.sha256((data_root / name).read_bytes()).hexdigest()
            for name in ("aspa_2015_2019_approval.csv", "aspa_earlier_sources.json")
        },
        "earlier_sources": {
            year: source["sha256"] for year, source in meta["sources"].items()
        },
        "evidence_windows_checked": checks,
        "recent_source_checks": {
            key: recent[key]
            for key in (
                "inputs",
                "sources",
                "legacy_2021_checks",
                "evidence_windows_checked",
            )
        },
        "check_scope": "Original PDF hashes, page anchors, exclusions, and bidirectional CEP forwarding/ATCM adoption lists for earlier requests; existing recent source checks rerun. Source reading defines requests and dispositions; no independent human coding or substantive-retention validation.",
        "results": comparison(earlier, recent["records"]),
        "earlier_records": earlier,
        "limitations": meta["interpretation_limits"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA)
    parser.add_argument(
        "--pdf-root", type=Path, default=ROOT.parent / "ats_corpus_data/pdfs"
    )
    parser.add_argument(
        "--out", type=Path, default=DATA / "aspa_historical_results.json"
    )
    args = parser.parse_args()
    result = build(args.data_root, args.pdf_root)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["results"], indent=2))
