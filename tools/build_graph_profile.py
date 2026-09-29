#!/usr/bin/env python3
"""Cache the complete retained graph and deduplicated input–outcome counts.

No source artifacts are changed. Missing links are not coded as failed proposals.
"""

from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/breakdown_profile"
SOURCES = [
    "decision_map.json",
    "revision/breakdown_exclusions.json",
    "tools/build_graph_profile.py",
]
EXPLICIT = {"direct_citation", "official_paragraph"}


def display_node(node):
    """Recover explicit paper-type tokens without changing the source graph."""
    result = {
        k: node[k]
        for k in (
            "id",
            "kind",
            "meeting",
            "year",
            "paper_type",
            "outcome_type",
            "placeholder",
        )
        if k in node
    }
    if node["kind"] == "paper" and not node.get("paper_type"):
        match = re.fullmatch(r"(?:ATCM\d+|SATCM\d+):(WP|IP|BP|SP) \d+", node["id"])
        if match:
            result["paper_type"] = match.group(1)
            result["paper_type_source"] = "canonical_identifier"
    return result


def build(graph, excluded):
    nodes = {n["id"]: n for n in graph["nodes"] if n["id"] not in excluded}
    edges = [e for e in graph["edges"] if e["src"] in nodes and e["dst"] in nodes]
    outcomes = {
        k: n
        for k, n in nodes.items()
        if n["kind"] == "outcome" and not n.get("placeholder")
    }
    pairs = defaultdict(set)
    for e in edges:
        if nodes[e["src"]]["kind"] == "paper" and e["dst"] in outcomes:
            pairs[e["src"], e["dst"]].add(e["channel"])
    incoming, explicit_incoming, outgoing = (
        defaultdict(set),
        defaultdict(set),
        defaultdict(set),
    )
    for (src, dst), channels in pairs.items():
        incoming[dst].add(src)
        outgoing[src].add(dst)
        if channels & EXPLICIT:
            explicit_incoming[dst].add(src)
    rows = [
        dict(
            id=k,
            outcome_type=n["outcome_type"],
            paper_count=len(incoming[k]),
            explicit_paper_count=len(explicit_incoming[k]),
        )
        for k, n in sorted(outcomes.items())
    ]
    by_type = []
    for kind in ("Recommendation", "Measure", "Decision", "Resolution"):
        selected = [r for r in rows if r["outcome_type"] == kind]
        by_type.append(
            dict(
                outcome_type=kind,
                n=len(selected),
                explicit=sum(r["explicit_paper_count"] > 0 for r in selected),
                candidate_only=sum(
                    r["paper_count"] > 0 and r["explicit_paper_count"] == 0
                    for r in selected
                ),
                no_link=sum(r["paper_count"] == 0 for r in selected),
            )
        )
    incident = {e[k] for e in edges for k in ("src", "dst")}
    summary = dict(
        nodes=len(nodes),
        edges=len(edges),
        kinds=dict(Counter(n["kind"] for n in nodes.values())),
        placeholders=sum(bool(n.get("placeholder")) for n in nodes.values()),
        isolates=len(set(nodes) - incident),
        outcomes=len(outcomes),
        linked_outcomes=len({dst for src, dst in pairs}),
        explicit_outcomes=sum(r["explicit_paper_count"] > 0 for r in rows),
        linked_papers=len(outgoing),
        pairs=len(pairs),
        explicit_pairs=sum(bool(c & EXPLICIT) for c in pairs.values()),
        multiple_input_outcomes=sum(r["paper_count"] > 1 for r in rows),
        multiple_input_explicit_outcomes=sum(
            r["explicit_paper_count"] > 1 for r in rows
        ),
        multiple_output_papers=sum(len(dsts) > 1 for dsts in outgoing.values()),
        degree_counts=dict(
            sorted(Counter(min(5, r["paper_count"]) for r in rows).items())
        ),
    )
    return dict(
        summary=summary,
        by_type=by_type,
        outcomes=rows,
        nodes=[display_node(n) for n in nodes.values()],
        edges=[{k: e[k] for k in ("src", "dst", "channel")} for e in edges],
        paper_pairs=[
            dict(
                paper=src,
                outcome=dst,
                channels=sorted(channels),
                explicit=bool(channels & EXPLICIT),
            )
            for (src, dst), channels in sorted(pairs.items())
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    path = OUT / "graph_profile.json"
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}
    if path.exists() and not args.refresh:
        result = json.loads(path.read_text())
        if result["source_sha256"] != hashes:
            raise SystemExit("Graph sources changed; rerun with --refresh.")
    else:
        result = build(
            json.loads((ROOT / SOURCES[0]).read_text()),
            json.loads((ROOT / SOURCES[1]).read_text()),
        )
        result["source_sha256"] = hashes
        OUT.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n")
        for key, filename in (
            ("outcomes", "graph_outcome_inputs.csv"),
            ("paper_pairs", "graph_paper_outcome_pairs.csv"),
        ):
            with (OUT / filename).open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=result[key][0].keys())
                writer.writeheader()
                writer.writerows(result[key])
    print(json.dumps(result["summary"], indent=2))
    print(json.dumps(result["by_type"], indent=2))


if __name__ == "__main__":
    main()
