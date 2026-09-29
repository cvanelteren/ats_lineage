"""Check a manually read ASPA cohort against original-report page windows.

Checks establish provenance and internal consistency, not independent legal or
historical validation. The input distinguishes plan reviews from adoption-stage
requests; the resulting fractions are not archive-wide proposal-success rates.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COHORT = ROOT / "research/breakdown_review/aspa_2021_cohort.json"


def normalise(text: str) -> str:
    # Preserve letters and words, but ignore PDF control characters. This does
    # NOT recover damaged glyphs or manufacture paragraph numbers.
    return " ".join("".join(c if c.isprintable() else " " for c in text).split())


def page_window(text: str, pages: list[int]) -> str:
    first, last = pages
    split = text.split("\f")
    if not 1 <= first <= last <= len(split):
        raise ValueError(f"invalid page window: {pages}")
    return normalise("\n".join(split[first - 1 : last]))


def check_plans(plans: list[dict]) -> None:
    identifiers = [p["aspa"] for p in plans]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate plan identity in annual cohort")
    allowed = {
        "approval": {"adopted", "cep_no_consensus"},
        "sgmp_review": {"referred_as_requested"},
        "retain_existing": {"retained_without_measure"},
    }
    adopted_measures = []
    for p in plans:
        if p["disposition"] not in allowed.get(p["requested_stage"], set()):
            raise ValueError(f"incompatible request and disposition: ASPA {p['aspa']}")
        if (p["disposition"] == "adopted") != isinstance(p["measure"], int):
            raise ValueError(f"adoption/Measure mismatch: ASPA {p['aspa']}")
        if p["measure"] is not None:
            adopted_measures.append(p["measure"])
        if "followup" in p and p["followup"]["year"] <= 2021:
            raise ValueError("follow-up must occur after the initial meeting")
    if len(set(adopted_measures)) != len(adopted_measures):
        raise ValueError("duplicate Measure within the 2021 cohort")


def summary(plans: list[dict]) -> dict:
    check_plans(plans)
    approval = [p for p in plans if p["requested_stage"] == "approval"]
    blocked = [p for p in approval if p["disposition"] == "cep_no_consensus"]
    followed = [p for p in blocked if "followup" in p]
    return {
        "plan_considerations": len(plans),
        "dispositions": dict(sorted(Counter(p["disposition"] for p in plans).items())),
        "adoption_stage_requests": len(approval),
        "adopted_at_initial_meeting": sum(
            p["disposition"] == "adopted" for p in approval
        ),
        "blocked_at_cep": len(blocked),
        "blocked_with_observed_followup": len(followed),
        "blocked_later_adopted": sum(
            p["followup"]["disposition"] == "adopted" for p in followed
        ),
        "by_kind_at_adoption_stage": {
            kind: {
                "requests": sum(p["kind"] == kind for p in approval),
                "adopted": sum(
                    p["kind"] == kind and p["disposition"] == "adopted"
                    for p in approval
                ),
            }
            for kind in sorted({p["kind"] for p in approval})
        },
        "substantive_proposal_acceptance": None,
        "historical_failure_trend": None,
        "interpretation": "One meeting's plan dispositions and subsequent agreement; requested substantive content and historical trends require separate analysis.",
    }


def check_measure_pair(text: str, measure: int, year: int, aspa: int) -> None:
    pattern = rf"Measure {measure} \({year}\)(.*?)(?=Measure \d+ \({year}\)|$)"
    matches = list(re.finditer(pattern, text))
    if not matches or not any(re.search(rf"\b{aspa}\b", m[1][:250]) for m in matches):
        raise ValueError(
            f"missing bounded adoption evidence: Measure {measure} ({year}), ASPA {aspa}"
        )


def build(cohort: Path, pdf_root: Path) -> dict:
    data = json.loads(cohort.read_text())
    if set(data["excluded_status_notices"]["aspas"]) & {
        p["aspa"] for p in data["plans"]
    }:
        raise ValueError("status-only notice also counted as a plan consideration")
    result = summary(data["plans"])
    texts, hashes = {}, {}
    for key, source in data["sources"].items():
        pdf = pdf_root / source["file"]
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"source hash mismatch: {key}")
        texts[key] = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        hashes[key] = digest
    windows = {}
    for name, evidence in data["evidence"].items():
        window = page_window(texts[evidence["source"]], evidence["pdf_pages"])
        if normalise(evidence["anchor"]) not in window:
            raise ValueError(f"missing anchor in declared pages: {name}")
        windows[name] = window
    for p in data["plans"]:
        if p["measure"] is not None:
            check_measure_pair(windows["adopted"], p["measure"], 2021, p["aspa"])
        if p.get("followup", {}).get("disposition") == "adopted":
            f = p["followup"]
            check_measure_pair(
                windows["followup_adopted"], f["measure"], f["year"], p["aspa"]
            )
    return {
        "input_sha256": hashlib.sha256(cohort.read_bytes()).hexdigest(),
        "source_sha256": hashes,
        "evidence_windows_checked": len(windows),
        "checks": "Original PDF hashes, declared page anchors, plan identities, request/disposition compatibility, and adopted number/year/area pairs. Paragraph numbering and substantive judgments require source reading.",
        "results": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument(
        "--pdf-root", type=Path, default=ROOT.parent / "ats_corpus_data/pdfs"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "research/breakdown_review/aspa_2021_results.json",
    )
    args = parser.parse_args()
    payload = build(args.cohort, args.pdf_root)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
