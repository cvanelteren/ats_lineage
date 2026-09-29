#!/usr/bin/env python3
"""Cache meeting dispositions and source-checked follow-up for six revisions."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/breakdown_review"


def build():
    paths = [BASE / "aspa_historical_results.json", BASE / "aspa_recent_results.json"]
    historical, recent = [json.loads(p.read_text()) for p in paths]
    annual = [
        {"year": r["year"], **r["by_kind"]["revision"]}
        for r in historical["results"]["annual"]
    ]
    # These are request episodes, not area identities: Biscoe has two episodes.
    followup = [
        (113, "Litchfield Island", 2021, 2022, 5),
        (119, "Davis Valley / Forlidas Pond", 2021, 2022, 7),
        (124, "Cape Crozier", 2021, 2022, 9),
        (139, "Biscoe Point: 2021 revision", 2021, 2022, 14),
        (145, "Port Foster", 2022, 2023, 10),
        (139, "Biscoe Point: marine extension", 2024, None, None),
    ]
    rows = recent["records"]
    failures = {
        (r["year"], r["request_id"])
        for r in rows
        if r["kind"] == "revision"
        and r["requested_stage"] == "approval"
        and r["atcm_disposition"] != "adopted"
    }
    assert failures == {(year, f"aspa{aspa}") for aspa, _, year, _, _ in followup}
    episodes = []
    for aspa, name, start, end, measure in followup:
        if end is not None:
            matches = [
                r for r in rows if r["year"] == end and r["request_id"] == f"aspa{aspa}"
            ]
            assert len(matches) == 1 and matches[0]["atcm_disposition"] == "adopted"
            assert matches[0]["measure"] == measure
        else:
            assert not any(
                r["year"] > start
                and r["request_id"] == f"aspa{aspa}"
                and r["atcm_disposition"] == "adopted"
                for r in rows
            )
        episodes.append(
            {
                "episode_id": f"aspa{aspa}-revision-{start}",
                "aspa": aspa,
                "name": name,
                "non_agreement_year": start,
                "adoption_year": end,
                "adopting_measure_number": measure,
                "followup_end": 2025,
                "followup_source": (
                    "ATCM 2022: ATCM 77–78, CEP 95–103"
                    if start == 2021
                    else (
                        "ATCM 2022: CEP 92, ATCM 80; ATCM 2023: CEP 103, ATCM 89"
                        if start == 2022
                        else "ATCM 2024: CEP 117–122, ATCM 75–92; 2025 itemised request/adoption series"
                    )
                ),
            }
        )
    return {
        "checked": "2026-09-28",
        "unit": "request at a meeting; repeated requests are dependent",
        "inputs": [
            {
                "path": str(p.relative_to(ROOT)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in paths
        ],
        "annual": annual,
        "delayed_episodes": episodes,
        "limits": "Follow-up links are source-based analytical readings, not inferred from shared area numbers alone. Later adoption does not establish retention of every provision. No adoption recorded by the endpoint is not permanent failure. ASPA 145 has a report discrepancy documented in the manuscript. Do not add later recoveries to annual adoption numerators.",
    }


if __name__ == "__main__":
    result = build()
    target = ROOT / "data/breakdown_profile/aspa_revision_profile.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Cached {len(result['annual'])} meetings and {len(result['delayed_episodes'])} delayed revision episodes."
    )
