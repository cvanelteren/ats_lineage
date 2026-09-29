#!/usr/bin/env python3
"""Cache title-defined Measure composition and source-checked legal-status cases.

Subject categories measure composition, not ambition, burden, implementation or
destination eligibility. Source graph and earlier analyses remain unchanged.
"""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/breakdown_profile"
SOURCES = (
    "decision_map.json",
    "official_outcome_counts.json",
    "revision/commitment_cases.json",
    "tools/build_commitment_profile.py",
)
AREA = re.compile(
    r"\bASPA\b|\bASMA\b|Specially Protected Area|Specially Managed Area|Management Plan",
    re.I,
)
HERITAGE = re.compile(r"Historic Site|Monument|Heritage", re.I)
LEGACY = re.compile(r"\bSPA\b|\bSSSI\b|Sites of Special Scientific Interest", re.I)


def subject(title):
    if not title or not title.strip():
        raise ValueError("Measure has no classifiable title")
    for name, rule in (("area", AREA), ("heritage", HERITAGE), ("legacy_area", LEGACY)):
        if rule.search(title):
            return name
    return "other"


def build(graph, curation, official):
    ids = [n["id"] for n in graph["nodes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate graph identifiers")
    rows = []
    for n in graph["nodes"]:
        if (
            n.get("kind") != "outcome"
            or n.get("placeholder")
            or not n["id"].startswith("Measure ")
            or (n.get("year") or 0) < 1995
        ):
            continue
        if not isinstance(n.get("meeting"), (int, float)):
            raise ValueError(f"Missing meeting: {n['id']}")
        rows.append(
            dict(
                id=n["id"],
                year=n["year"],
                meeting=n["meeting"],
                regular=isinstance(n["meeting"], int),
                title=n.get("title"),
                subject=subject(n.get("title")),
            )
        )
    rows.sort(key=lambda r: (r["year"], r["id"]))
    regular = [r for r in rows if r["regular"]]
    expected = official["sources"]["atcm_19_47"]["type_counts"]["Measure"]
    if len(regular) != expected:
        raise ValueError(
            f"Recovered/official regular Measure counts differ: {len(regular)}/{expected}"
        )
    other_ids = {r["id"] for r in rows if r["subject"] == "other"}
    cases = curation["cases"]
    if (
        len({c["id"] for c in cases}) != len(cases)
        or {c["id"] for c in cases} != other_ids
    ):
        raise ValueError("Curation must cover every outside-class Measure exactly once")
    for c in cases:
        if (c["status"] == "effective") != bool(c["effective_date"]):
            raise ValueError(f"Inconsistent effective date/status: {c['id']}")
        if c["effective_date"] and c["effective_date"] > curation["checked_on"]:
            raise ValueError("Effective date after status snapshot")
    by_meeting = defaultdict(Counter)
    years = {}
    for r in regular:
        by_meeting[r["meeting"]][r["subject"]] += 1
        years[r["meeting"]] = r["year"]
    annual = [
        dict(
            meeting=m,
            year=years[m],
            total=sum(cs.values()),
            **{s: cs[s] for s in ("area", "heritage", "legacy_area", "other")},
        )
        for m, cs in sorted(by_meeting.items())
    ]

    def summary(selected):
        counts = Counter(r["subject"] for r in selected)
        return dict(
            n=len(selected),
            subjects=dict(counts),
            area_or_heritage=len(selected) - counts["other"],
            other=counts["other"],
        )

    return dict(
        schema_version=1,
        classification="Mutually exclusive title subjects; modern area, heritage, legacy area, other, in that order",
        snapshot=curation["checked_on"],
        all_measures=summary(rows),
        regular=summary(regular),
        since_2010=summary([r for r in regular if r["year"] >= 2010]),
        last_other_year=max(r["year"] for r in rows if r["subject"] == "other"),
        case_statuses=dict(Counter(c["status"] for c in cases)),
        measures=rows,
        meetings=annual,
        cases=cases,
        histories=curation["histories"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    hashes = {s: hashlib.sha256((ROOT / s).read_bytes()).hexdigest() for s in SOURCES}
    target = OUT / "commitment_profile.json"
    if target.exists() and not args.refresh:
        old = json.loads(target.read_text())
        if old.get("source_hashes") == hashes:
            print("Reusing verified commitment cache")
            return
    result = build(
        *(
            json.loads((ROOT / s).read_text())
            for s in (
                "decision_map.json",
                "revision/commitment_cases.json",
                "official_outcome_counts.json",
            )
        )
    )
    result["source_hashes"] = hashes
    OUT.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    for name, rows in (
        ("measure_subjects", result["measures"]),
        ("measure_meetings", result["meetings"]),
    ):
        with (OUT / f"{name}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "regular",
                    "all_measures",
                    "since_2010",
                    "last_other_year",
                    "case_statuses",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
