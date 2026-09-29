"""Reconstruct annual plan dispositions, keeping stages and request kinds separate.

This checks a manually read series, not the accuracy of autonomous extraction.
It verifies original PDF provenance and bounded evidence, but does not infer
substantive success from adoption, absence of a link, or an area identifier.
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
    from tools.check_aspa_cohort import (
        build as check_2021,
        check_measure_pair,
        normalise,
        page_window,
    )
except ModuleNotFoundError:  # Running the script directly from the repository.
    from check_aspa_cohort import (
        build as check_2021,
        check_measure_pair,
        normalise,
        page_window,
    )

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/breakdown_review"


def load_rows(data_root: Path = DATA) -> list[dict]:
    base = json.loads((data_root / "aspa_2021_cohort.json").read_text())
    dispositions = {
        "adopted": ("approved", "adopted"),
        "cep_no_consensus": ("no_consensus", "not_adopted_after_cep"),
        "referred_as_requested": ("referred", "not_at_adoption_stage"),
        "retained_without_measure": ("retained", "no_new_measure_required"),
    }
    rows = []
    for plan in base["plans"]:
        cep, atcm = dispositions[plan["disposition"]]
        rows.append(
            {
                "year": 2021,
                "request_id": f"aspa{plan['aspa']}",
                "area_ids": [plan["aspa"]],
                "kind": plan["kind"],
                "requested_stage": {"sgmp_review": "review"}.get(
                    plan["requested_stage"], plan["requested_stage"]
                ),
                "cep_disposition": cep,
                "atcm_disposition": atcm,
                "measure": plan["measure"],
                "wp": plan["wp"],
                "evidence": "aspa_2021_cohort.json",
                "note": "Imported from separately checked 2021 cohort; no new substantive coding.",
            }
        )
    with (data_root / "aspa_2022_2025_requests.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            if None in row or any(value is None for value in row.values()):
                raise ValueError("malformed CSV row")
            row["year"] = int(row["year"])
            row["area_ids"] = [
                int(value) for value in row["area_ids"].split("|") if value
            ]
            for key in ("wp", "measure"):
                row[key] = int(row[key]) if row[key] else None
            rows.append(row)
    return rows


def blocked(row: dict) -> bool:
    # One request, even if both forums explicitly record non-consensus.
    return (
        row["cep_disposition"] == "no_consensus"
        or row["atcm_disposition"] == "no_consensus"
    )


def validate_rows(rows: list[dict]) -> None:
    identities, measures, areas = set(), set(), set()
    for row in rows:
        identity = (row["year"], row["request_id"])
        if identity in identities:
            raise ValueError("duplicate request within a meeting")
        identities.add(identity)
        for area in row["area_ids"]:
            if (row["year"], area) in areas:
                raise ValueError("area counted twice within a meeting")
            areas.add((row["year"], area))
        stage, cep, atcm = (
            row["requested_stage"],
            row["cep_disposition"],
            row["atcm_disposition"],
        )
        allowed = {
            "approval": {
                ("approved", "adopted"),
                ("approved_after_change", "adopted"),
                ("approved", "pending_external_approval"),
                ("no_consensus", "not_adopted_after_cep"),
                ("no_consensus", "no_consensus"),
                ("continued_discussion", "no_consensus"),
            },
            "review": {("referred", "not_at_adoption_stage")},
            "retain_existing": {("retained", "no_new_measure_required")},
        }
        if (cep, atcm) not in allowed.get(stage, set()):
            raise ValueError(f"incompatible stage and disposition: {identity}")
        if row["kind"] not in {
            "revision",
            "new_designation",
            "merger",
            "dedesignation",
            "review_without_change",
        }:
            raise ValueError("unknown request kind")
        measure = row["measure"]
        if (atcm == "adopted") != (type(measure) is int and measure > 0):
            raise ValueError("adoption/Measure mismatch")
        if atcm != "adopted" and measure is not None:
            raise ValueError("unadopted request has a Measure")
        if measure is not None:
            key = (row["year"], measure)
            if key in measures:
                raise ValueError("duplicate year-specific Measure")
            measures.add(key)
            if len(row["area_ids"]) != 1:
                raise ValueError("adopted plan needs its final area identifier")


def summarize(rows: list[dict]) -> dict:
    validate_rows(rows)
    annual = []
    for year in sorted({row["year"] for row in rows}):
        current = [row for row in rows if row["year"] == year]
        approval = [row for row in current if row["requested_stage"] == "approval"]
        adopted = sum(row["atcm_disposition"] == "adopted" for row in approval)
        failed = sum(blocked(row) for row in approval)
        external = sum(
            row["atcm_disposition"] == "pending_external_approval" for row in approval
        )
        if adopted + failed + external != len(approval):
            raise ValueError("approval dispositions do not partition the population")
        annual.append(
            {
                "year": year,
                "plan_considerations": len(current),
                "approval_stage_requests": len(approval),
                "adopted": adopted,
                "recorded_non_agreement": failed,
                "awaiting_external_approval": external,
                "earlier_stage_referrals": sum(
                    row["requested_stage"] == "review" for row in current
                ),
                "unchanged_reviews": sum(
                    row["requested_stage"] == "retain_existing" for row in current
                ),
                "adopted_fraction": adopted / len(approval) if approval else None,
                "non_agreement_fraction": failed / len(approval) if approval else None,
                "by_kind": {
                    kind: {
                        "approval_stage_requests": sum(
                            row["kind"] == kind for row in approval
                        ),
                        "adopted": sum(
                            row["kind"] == kind and row["atcm_disposition"] == "adopted"
                            for row in approval
                        ),
                        "recorded_non_agreement": sum(
                            row["kind"] == kind and blocked(row) for row in approval
                        ),
                        "awaiting_external_approval": sum(
                            row["kind"] == kind
                            and row["atcm_disposition"] == "pending_external_approval"
                            for row in approval
                        ),
                    }
                    for kind in sorted({row["kind"] for row in approval})
                },
            }
        )
    return {
        "annual": annual,
        "annual_record_count": len(rows),
        "unit": "request at a meeting, not unique proposal or independent trial",
        "non_agreement_scope": "CEP or ATCM only. The 2023 pending-external case follows reported CCAMLR non-consensus, which remains outside this count.",
        "substantive_proposal_acceptance": None,
        "historical_loss_of_capacity": None,
        "all_subject_veto_frequency": None,
        "interpretation": "Recent annual dispositions distinguish non-agreement, external approval, and ordinary review. Content retention and earlier-period comparisons remain necessary for the breakdown claim.",
    }


def adoption_pairs(text: str, year: int) -> set[tuple[int, int]]:
    """Only call on a window beginning with the ATCM's adoption list."""
    pairs = set()
    for match in re.finditer(
        rf"Measure (\d+) \({year}\)(.*?)(?=Measure \d+ \(\d{{4}}\)|$)", text
    ):
        area = re.search(
            r"Antarctic Specially Protected Area\s+(?:ASPA\s+)?(?:No\.?\s+)?(\d+)",
            match[2][:250],
        )
        if area:
            pairs.add((int(match[1]), int(area[1])))
    return pairs


def build(data_root: Path, pdf_root: Path) -> dict:
    rows = load_rows(data_root)
    result = summarize(rows)
    meta = json.loads((data_root / "aspa_recent_sources.json").read_text())
    legacy = check_2021(data_root / "aspa_2021_cohort.json", pdf_root)
    evidence_checks = []
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
            evidence_checks.append(f"{year}/{key}")
        current = [row for row in rows if row["year"] == year]
        if set(source["excluded_status_areas"]) & {
            a for row in current for a in row["area_ids"]
        }:
            raise ValueError(f"status notice counted as considered plan: {year}")
        for row in current:
            if row["evidence"] not in windows:
                raise ValueError("missing evidence window for request")
            request_text = windows[row["evidence"]]
            name = meta["request_names"].get(row["request_id"])
            numbered = bool(row["area_ids"]) and all(
                re.search(rf"\b{area}\b", request_text) for area in row["area_ids"]
            )
            named = bool(name) and normalise(name) in request_text
            if not numbered and not named:
                raise ValueError(
                    f"request absent from evidence: {year}/{row['request_id']}"
                )
        adopted = [row for row in current if row["atcm_disposition"] == "adopted"]
        for row in adopted:
            check_measure_pair(
                windows["adopted"], row["measure"], year, row["area_ids"][0]
            )
        # Bidirectional reconciliation: do not merely verify the selected rows.
        listed = adoption_pairs(
            windows["adopted"].split(
                "The Meeting adopted the following Measures on Protected Areas", 1
            )[-1],
            year,
        )
        if year == 2022:
            listed = adoption_pairs(
                windows["adopted"].split("Accepting the CEP’s advice", 1)[-1], year
            )
        coded = {(row["measure"], row["area_ids"][0]) for row in adopted}
        if listed != coded:
            raise ValueError(
                f"adoption list mismatch for {year}: missing={listed-coded}, extra={coded-listed}"
            )
    return {
        "inputs": {
            name: hashlib.sha256((data_root / name).read_bytes()).hexdigest()
            for name in (
                "aspa_2021_cohort.json",
                "aspa_2022_2025_requests.csv",
                "aspa_recent_sources.json",
            )
        },
        "sources": {year: source["sha256"] for year, source in meta["sources"].items()},
        "legacy_2021_checks": legacy,
        "evidence_windows_checked": evidence_checks,
        "check_scope": "Original PDF hashes; declared page anchors; area mentions; year/Measure/area adoption pairs in both directions; stage consistency. Not independent historical or provision-level validation.",
        "source_discrepancies": meta["source_discrepancies"],
        "results": result,
        "records": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA)
    parser.add_argument(
        "--pdf-root", type=Path, default=ROOT.parent / "ats_corpus_data/pdfs"
    )
    parser.add_argument("--out", type=Path, default=DATA / "aspa_recent_results.json")
    args = parser.parse_args()
    payload = build(args.data_root, args.pdf_root)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(payload["results"], indent=2))
