#!/usr/bin/env python3
"""Draw every retained node/edge and show input–outcome counts from cached data."""

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ats-breakdown-mpl")
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from plot_breakdown_profile import uplt, panel, save, BLUE, TEAL, GREY

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data/breakdown_profile/graph_profile.json").read_text())
for source, expected in D["source_sha256"].items():
    if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != expected:
        raise RuntimeError(
            "Stale graph cache: run tools/build_graph_profile.py --refresh"
        )


def positions(nodes):
    """Meeting is x; lanes and stable within-meeting spacing are display only."""
    groups = defaultdict(list)
    for n in nodes:
        groups[n["kind"], n["meeting"]].append(n["id"])
    pos = {}
    levels = {"paper": 2.0, "outcome": 1.0, "report": 0.0}
    for (kind, meeting), ids in sorted(groups.items()):
        ordered = sorted(ids)
        for i, node_id in enumerate(ordered):
            # A narrow three-column stack separates individual paper glyphs.
            col = i % 3 if kind == "paper" else 1
            row = i // 3 if kind == "paper" else i
            nrows = int(np.ceil(len(ordered) / 3)) if kind == "paper" else len(ordered)
            dy = 0.76 * ((row + 0.5) / nrows - 0.5) if nrows > 1 else 0.0
            pos[node_id] = (meeting + (col - 1) * 0.14, levels[kind] + dy)
    return pos


def graph(ax, large=False):
    nodes = {n["id"]: n for n in D["nodes"]}
    pos = positions(D["nodes"])
    assert set(pos) == set(nodes)
    colors = {"paper": BLUE, "outcome": TEAL, "report": GREY}
    # All channels and isolates remain visible; no weight or centrality filter.
    for kind in ("outcome", "paper"):
        segments = [
            [pos[e["src"]], pos[e["dst"]]]
            for e in D["edges"]
            if nodes[e["src"]]["kind"] == kind
        ]
        ax.add_collection(
            LineCollection(
                segments,
                colors=colors[kind],
                linewidths=0.22 if large else 0.18,
                alpha=0.13,
                zorder=1,
            )
        )
    for kind in ("paper", "outcome", "report"):
        selected = [
            n for n in D["nodes"] if n["kind"] == kind and not n.get("placeholder")
        ]
        xy = np.array([pos[n["id"]] for n in selected])
        ax.scatter(
            xy[:, 0],
            xy[:, 1],
            s=(2.0 if kind == "paper" else 5.0) * (1.5 if large else 1),
            color=colors[kind],
            linewidths=0,
            zorder=3,
        )
    xy = np.array([pos[n["id"]] for n in D["nodes"] if n.get("placeholder")])
    ax.scatter(
        xy[:, 0],
        xy[:, 1],
        s=6,
        facecolor="white",
        edgecolor=TEAL,
        linewidths=0.5,
        zorder=4,
    )
    ax.format(
        xlim=(0, 48),
        ylim=(-0.25, 2.5),
        yticks=[0, 1, 2],
        yticklabels=["Reports", "Formal outcomes", "Submitted papers"],
        xticks=[1, 10, 20, 30, 40, 47],
        xlabel="Regular meeting number",
        yticklen=0,
        ytickloc="left",
        yticklabelloc="left",
        abc=not large,
    )
    ax.spines["left"].set_visible(False)
    ax.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="o",
                color="none",
                markeredgecolor=TEAL,
                markerfacecolor="white",
                markersize=4,
                label="Outcome known only from a citation",
            )
        ],
        loc="t",
        frameon=False,
        fontsize=7,
    )


def main():
    fig, axes = uplt.subplots(
        [[1, 1], [2, 3]],
        figwidth=7.1,
        ref=2,
        refaspect=1,
        hratios=[0.85, 1],
        share=False,
        span=False,
    )
    a, b, c = axes
    graph(a)
    a.format(abc="a", abcweight="bold")
    panel(b, "b")
    rows = D["by_type"]
    xx = np.arange(len(rows))
    bottom = np.zeros(len(rows))
    for key, color, label in (
        ("explicit", BLUE, "Report-channel link"),
        ("candidate_only", "#B8D0DE", "Candidate links only"),
        ("no_link", "#E3E6E8", "No paper link found"),
    ):
        values = np.array([r[key] for r in rows])
        b.bar(xx, values, bottom=bottom, color=color, width=0.62, label=label)
        bottom += values
    b.format(
        xticks=xx,
        xticklabels=["Recom-\nmendation", "Measure", "Decision", "Resolution"],
        ylim=(0, 385),
        ylabel="Formal outcomes in the graph",
        xticklabelsize=7,
    )
    b.legend(frameon=False, fontsize=7, loc="upper left", ncols=1)
    panel(c, "c")
    counts = D["summary"]["degree_counts"]
    c.bar(range(6), [counts.get(str(i), 0) for i in range(6)], color=TEAL, width=0.62)
    c.format(
        xticks=range(6),
        xticklabels=["0", "1", "2", "3", "4", "5+"],
        ylim=(0, 385),
        xlabel="Distinct papers linked to an outcome",
        ylabel="Formal outcomes in the graph",
    )
    save(fig, "breakdown_graph_inputs")
    fig, ax = uplt.subplots(figwidth=14, figheight=6, share=False, span=False)
    graph(ax, large=True)
    save(fig, "breakdown_full_graph")
    print("Wrote input–outcome figure and enlarged complete graph as PDF/SVG/PNG.")


if __name__ == "__main__":
    main()
