#!/usr/bin/env python3
"""Opening figure: routed full graph and conditional link proportions.

Routing changes geometry only. No nodes, edges, or evidence are added or
removed. Shared control points are display guides, not inferred communities.
"""

from collections import Counter
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ats-breakdown-mpl")
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from plot_graph_profile import D, positions
from plot_breakdown_profile import uplt, panel, save, BLUE, TEAL, GREY

OUTCOMES = ("Recommendation", "Measure", "Decision", "Resolution")
SHORT = ("Recom.", "Measure", "Decision", "Resolution")
PAPERS = ("WP", "IP")
# Marker areas are in points squared: enlargement must not alter coordinates.
# Papers are already crowded at print size, so enlarge them less than reports.
NODE_AREAS = {"paper": 3.0, "outcome": 9.5, "report": 12.0}
UNRESOLVED_AREA = 10.0
HEATMAP_CMAP = "Blues"
TEXT_DARK = "#0B1721"


def relative_luminance(color):
    """Linear-light luminance, used only for readable cell annotations."""
    rgb = np.asarray(to_rgb(color))
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(linear @ np.array([0.2126, 0.7152, 0.0722]))


def annotation_color(background):
    light = relative_luminance(background)
    dark = relative_luminance(TEXT_DARK)
    white_contrast = 1.05 / (light + 0.05)
    dark_contrast = (max(light, dark) + 0.05) / (min(light, dark) + 0.05)
    return "white" if white_contrast > dark_contrast else TEXT_DARK


def matrices(data):
    nodes = {n["id"]: n for n in data["nodes"]}
    paper_pairs = {(p["paper"], p["outcome"]) for p in data["paper_pairs"]}
    paper_counts = Counter(
        (nodes[dst]["outcome_type"], nodes[src].get("paper_type", "Unknown"))
        for src, dst in paper_pairs
    )
    if any(kind not in PAPERS for _, kind in paper_counts):
        raise ValueError(
            "Unresolved or unsupported paper type: do not silently drop links"
        )
    # Stored edges point from the cited instrument to the citing instrument.
    citations = {
        (e["src"], e["dst"])
        for e in data["edges"]
        if e["channel"] == "outcome_text_label"
        and nodes[e["src"]]["kind"] == nodes[e["dst"]]["kind"] == "outcome"
        and not nodes[e["src"]].get("placeholder")
        and not nodes[e["dst"]].get("placeholder")
    }
    cite_counts = Counter(
        (nodes[dst]["outcome_type"], nodes[src]["outcome_type"])
        for src, dst in citations
    )
    papers = np.array([[paper_counts[o, p] for p in PAPERS] for o in OUTCOMES])
    cites = np.array([[cite_counts[a, b] for b in OUTCOMES] for a in OUTCOMES])
    assert papers.sum() == len(paper_pairs)
    assert cites.sum() == len(citations)
    return papers, cites


def row_proportions(counts):
    """P(column type | row type, recovered distinct link); empty rows undefined."""
    counts = np.asarray(counts, dtype=float)
    if counts.ndim != 2 or not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError("Expected a finite non-negative count matrix")
    totals = counts.sum(axis=1, keepdims=True)
    return np.divide(counts, totals, out=np.full_like(counts, np.nan), where=totals > 0)


def routed_path(edge, nodes, pos, samples=48):
    """Cubic curves share meeting-level guides and keep their exact endpoints."""
    src, dst = nodes[edge["src"]], nodes[edge["dst"]]
    start, end = np.array(pos[src["id"]]), np.array(pos[dst["id"]])
    x0, x1 = src["meeting"], dst["meeting"]
    if src["kind"] == dst["kind"]:
        # Citations arch above the outcome band, with longer spans higher.
        height = 2.05 + 0.52 * min(abs(x1 - x0) / 25, 1)
        c1 = np.array([x0 + 0.20 * (x1 - x0), height])
        c2 = np.array([x1 - 0.20 * (x1 - x0), height])
        if x0 == x1:
            c1[0], c2[0] = x0 - 0.4, x1 + 0.4
    else:
        # Use the same guides for every pair of meeting/type bands.
        levels = {"paper": 3.0, "outcome": 1.5, "report": 0.0}
        y0, y1 = levels[src["kind"]], levels[dst["kind"]]
        c1 = np.array([x0, y0 + 0.65 * (y1 - y0)])
        c2 = np.array([x1, y1 - 0.65 * (y1 - y0)])
    t = np.linspace(0, 1, samples)[:, None]
    path = (1 - t) ** 3 * start + 3 * (1 - t) ** 2 * t * c1
    path += 3 * (1 - t) * t**2 * c2 + t**3 * end
    assert np.allclose(path[0], start) and np.allclose(path[-1], end)
    return path


def routed_graph(ax, data=D, large=False):
    nodes = {n["id"]: n for n in data["nodes"]}
    pos = positions(data["nodes"])
    # Open up the lanes without changing meeting positions or within-lane order.
    pos = {
        key: (x, y + {"paper": 1.0, "outcome": 0.5, "report": 0.0}[nodes[key]["kind"]])
        for key, (x, y) in pos.items()
    }
    assert set(pos) == set(nodes)
    drawn = 0
    # Separate the three link families without filtering or weighting edges.
    # The dense citation arches stay behind the paper links and node faces.
    styles = (
        ("outcome", "report", GREY, 0.07),
        ("outcome", "outcome", TEAL, 0.075),
        ("paper", "outcome", BLUE, 0.23),
    )
    for source, destination, color, opacity in styles:
        edges = [
            e
            for e in data["edges"]
            if nodes[e["src"]]["kind"] == source
            and nodes[e["dst"]]["kind"] == destination
        ]
        paths = [routed_path(e, nodes, pos) for e in edges]
        ax.add_collection(
            LineCollection(
                paths,
                colors=color,
                alpha=opacity,
                linewidths=0.35 if large else 0.28,
                capstyle="round",
                zorder=1,
            )
        )
        drawn += len(paths)
    assert drawn == len(data["edges"])
    for kind, color in (("paper", BLUE), ("outcome", TEAL), ("report", GREY)):
        xy = np.array(
            [
                pos[n["id"]]
                for n in nodes.values()
                if n["kind"] == kind and not n.get("placeholder")
            ]
        )
        ax.scatter(
            xy[:, 0],
            xy[:, 1],
            color=color,
            s=NODE_AREAS[kind] * (1.5 if large else 1),
            edgecolors="white" if kind == "outcome" else "none",
            linewidths=0.22 if kind == "outcome" else 0,
            zorder=3,
        )
    xy = np.array([pos[n["id"]] for n in nodes.values() if n.get("placeholder")])
    ax.scatter(
        xy[:, 0],
        xy[:, 1],
        s=UNRESOLVED_AREA * (1.5 if large else 1),
        facecolor="white",
        edgecolor=TEAL,
        linewidths=0.6,
        zorder=4,
    )
    ax.format(
        xlim=(0, 48),
        ylim=(-0.25, 3.5),
        yticks=[0, 1.5, 3],
        yticklabels=["Reports", "Formal outcomes", "Submitted papers"],
        xticks=[1, 10, 20, 30, 40, 47],
        xlabel="Regular meeting number",
        yticklen=0,
        ytickloc="left",
        yticklabelloc="left",
        ygrid=False,
        yticklabelsize=8.5,
        abc=False if large else "a",
        abcweight="bold",
    )
    ax.spines["left"].set_visible(False)
    # Figure 1's caption already explains open nodes; retain a key on the
    # standalone enlarged graph, where the caption is not present.
    if large:
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
            fontsize=8,
        )


def heatmap(ax, counts, columns, xlabel, ylabel, letter, title):
    panel(ax, letter, title)
    values = row_proportions(counts) * 100
    m = ax.pcolormesh(
        np.arange(len(columns) + 1) - 0.5,
        np.arange(5) - 0.5,
        np.ma.masked_invalid(values),
        cmap=HEATMAP_CMAP,
        vmin=0,
        vmax=100,
        discrete=False,
        edgecolors="white",
        linewidth=1.0,
    )
    for row, col in np.ndindex(values.shape):
        value = values[row, col]
        label = (
            "—"
            if not np.isfinite(value)
            else f"{value:.1f}%" if 0 < value < 100 else f"{value:.0f}%"
        )
        ax.text(
            col,
            row,
            label,
            ha="center",
            va="center",
            color=(
                annotation_color(m.cmap(m.norm(value)))
                if np.isfinite(value)
                else TEXT_DARK
            ),
            fontsize=9,
        )
    ax.format(
        xticks=np.arange(len(columns)),
        xticklabels=columns,
        yticks=np.arange(4),
        yticklabels=[
            f"{name} ({int(n):,})" for name, n in zip(SHORT, counts.sum(axis=1))
        ],
        ylim=(3.5, -0.5),
        xlabel=xlabel,
        ylabel=ylabel,
        xgrid=False,
        ygrid=False,
        xticklen=0,
        yticklen=0,
        xticklabelsize=8,
        yticklabelsize=8,
        ytickloc="left",
        yticklabelloc="left",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    return m


def opening_figure(data=D):
    papers, cites = matrices(data)
    fig, axes = uplt.subplots(
        [[1, 1], [2, 3]],
        figwidth=7.1,
        ref=2,
        refaspect=1,
        hratios=[1.16, 1],
        share=False,
        span=False,
    )
    routed_graph(axes[0], data=data)
    heatmap(
        axes[1],
        papers,
        ("Working", "Information"),
        "Linked paper type",
        "Outcome type",
        "b",
        "Paper–outcome links",
    )
    mesh = heatmap(
        axes[2],
        cites,
        SHORT,
        "Cited instrument",
        "Citing instrument",
        "c",
        "Instrument citations",
    )
    fig.colorbar(
        mesh,
        loc="b",
        cols=(1, 2),
        label="Share of links in each row (%)",
        ticks=[0, 25, 50, 75, 100],
        length=0.55,
        width=".7em",
    )
    return fig, axes


def main():
    fig, axes = opening_figure()
    save(fig, "breakdown_graph_opening")
    fig, ax = uplt.subplots(figwidth=14, figheight=6, share=False, span=False)
    routed_graph(ax, large=True)
    save(fig, "breakdown_full_graph_routed")
    papers, cites = matrices(D)
    print(f"All {len(D['nodes'])} nodes and {len(D['edges'])} edges retained.")
    print(
        f"Heatmaps: {papers.sum()} paper–outcome pairs; {cites.sum()} citation pairs."
    )


if __name__ == "__main__":
    main()
