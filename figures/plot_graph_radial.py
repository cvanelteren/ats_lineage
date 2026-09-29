#!/usr/bin/env python3
"""Chronological radial view of the complete retained document graph.

Meeting order is clockwise, with an open gap between the endpoints. Sector
width accommodates the paper inventory; angle is not elapsed time. Rings and
curve control points are display guides, not inferred communities or stages.
"""

from collections import defaultdict
import argparse
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from plot_graph_opening import D, matrices
from plot_graph_composition import composition_bars, PAPER_COLORS, INSTRUMENT_COLORS
from plot_breakdown_profile import uplt, save

REPORT_COLOR = "#343C4A"
START_ANGLE = np.deg2rad(66)
SWEEP = np.deg2rad(312)
BANDS = {
    "paper": (0.94, 1.16, 11),
    "outcome": (0.65, 0.80, 6),
    "report": (0.39, 0.39, 1),
}
RADIAL_AREAS = {"paper": 1.8, "outcome": 8.0, "report": 15.0}


def polar_point(theta, radius):
    return np.array([radius * np.cos(theta), radius * np.sin(theta)])


def radial_positions(nodes):
    """Pack every identity once; allocate meeting wedges for readable dots."""
    groups = defaultdict(list)
    for node in nodes:
        groups[node["meeting"], node["kind"]].append(node)
    meetings = sorted({node["meeting"] for node in nodes})
    # Eleven radial rows give each paper similar space around the outer band.
    # A minimum wedge preserves early/special meetings with very few papers.
    weights = np.array(
        [max(8, np.ceil(len(groups[m, "paper"]) / 11)) for m in meetings]
    )
    gap = np.deg2rad(0.48)
    widths = (SWEEP - gap * (len(meetings) - 1)) * weights / weights.sum()
    result, sectors = {}, {}
    cursor = START_ANGLE
    for meeting, width in zip(meetings, widths):
        high, low = cursor, cursor - width
        middle = (high + low) / 2
        sectors[meeting] = (high, low, middle)
        for kind, (inner, outer, nrows) in BANDS.items():
            items = sorted(groups[meeting, kind], key=lambda n: n["id"])
            columns = max(1, int(np.ceil(len(items) / nrows)))
            for index, node in enumerate(items):
                column, row = divmod(index, nrows)
                theta = high - width * (column + 0.5) / columns
                radius = (
                    (inner + outer) / 2
                    if nrows == 1
                    else inner + (outer - inner) * (row + 0.5) / nrows
                )
                result[node["id"]] = polar_point(theta, radius)
        cursor = low - gap
    assert len(result) == len(nodes)
    return result, sectors


def radial_path(edge, nodes, pos, sectors, samples=64):
    """Retain exact endpoints while curving links through meeting guides."""
    src, dst = nodes[edge["src"]], nodes[edge["dst"]]
    start, end = pos[src["id"]], pos[dst["id"]]
    t0, t1 = sectors[src["meeting"]][2], sectors[dst["meeting"]][2]
    if src["kind"] == dst["kind"] == "outcome":
        # Internal chords show cross-meeting citations. Same-meeting links
        # stay locally curved instead of collapsing to one radial segment.
        r = 0.27 if src["meeting"] != dst["meeting"] else 0.54
        c1, c2 = polar_point(t0 + 0.025, r), polar_point(t1 - 0.025, r)
    elif dst["kind"] == "report":
        c1, c2 = polar_point(t0, 0.48), polar_point(t1, 0.44)
    else:
        c1, c2 = polar_point(t0, 0.86), polar_point(t1, 0.84)
    t = np.linspace(0, 1, samples)[:, None]
    path = (
        (1 - t) ** 3 * start
        + 3 * (1 - t) ** 2 * t * c1
        + 3 * (1 - t) * t**2 * c2
        + t**3 * end
    )
    return path


def node_color(node):
    if node["kind"] == "paper":
        return PAPER_COLORS[node["paper_type"]]
    if node["kind"] == "outcome":
        return INSTRUMENT_COLORS[node["outcome_type"]]
    return REPORT_COLOR


def radial_graph(ax, data=D, *, large=False):
    nodes = {node["id"]: node for node in data["nodes"]}
    pos, sectors = radial_positions(data["nodes"])
    drawn = 0
    styles = (
        ("outcome", "report", 0.16, 0.35),
        ("outcome", "outcome", 0.29, 0.45),
        ("paper", "outcome", 0.34, 0.45),
    )
    for source, destination, opacity, width in styles:
        edges = [
            edge
            for edge in data["edges"]
            if nodes[edge["src"]]["kind"] == source
            and nodes[edge["dst"]]["kind"] == destination
        ]
        paths = [radial_path(edge, nodes, pos, sectors) for edge in edges]
        colors = [
            REPORT_COLOR if destination == "report" else node_color(nodes[e["src"]])
            for e in edges
        ]
        ax.add_collection(
            LineCollection(
                paths,
                colors=colors,
                alpha=opacity,
                linewidths=width,
                capstyle="round",
                zorder=1,
            )
        )
        drawn += len(edges)
    assert drawn == len(data["edges"])

    for kind in BANDS:
        selected = [
            node
            for node in nodes.values()
            if node["kind"] == kind and not node.get("placeholder")
        ]
        xy = np.array([pos[node["id"]] for node in selected])
        ax.scatter(
            xy[:, 0],
            xy[:, 1],
            s=RADIAL_AREAS[kind] * (1.35 if large else 1),
            color=[node_color(node) for node in selected],
            edgecolors="white" if kind != "paper" else "none",
            linewidths=0.25 if kind != "paper" else 0,
            zorder=3,
        )
    unresolved = [node for node in nodes.values() if node.get("placeholder")]
    xy = np.array([pos[node["id"]] for node in unresolved])
    ax.scatter(
        xy[:, 0],
        xy[:, 1],
        s=10 * (1.35 if large else 1),
        facecolors="white",
        edgecolors=[node_color(node) for node in unresolved],
        linewidths=0.75,
        zorder=4,
    )

    # Labels fit inside the intentional gap, not on top of the graph.
    counts = {
        kind: sum(node["kind"] == kind for node in nodes.values()) for kind in BANDS
    }
    labelsize = 11 if large else 8.5
    for radius, label in (
        (1.06, f"{counts['paper']:,} papers"),
        (0.73, f"{counts['outcome']:,} outcomes"),
        (0.42, f"{counts['report']:,} reports"),
    ):
        ax.text(
            0,
            radius,
            label,
            ha="center",
            va="center",
            fontsize=labelsize,
            color=REPORT_COLOR,
        )
    for meeting in (1, 10, 20, 30, 40, 47):
        theta = sectors[meeting][2]
        p0, p1 = polar_point(theta, 1.19), polar_point(theta, 1.22)
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], color="#788490", lw=0.65, zorder=0)
        year = next(
            node["year"] for node in nodes.values() if node["meeting"] == meeting
        )
        label = str(year)
        point = polar_point(theta, 1.28)
        ax.text(
            *point,
            label,
            ha="center",
            va="center",
            fontsize=labelsize,
            color=REPORT_COLOR,
        )
    ax.format(
        xlim=(-1.38, 1.38),
        ylim=(-1.38, 1.38),
        aspect="equal",
        xticks=[],
        yticks=[],
        grid=False,
        abc=False if large else "a",
        abcweight="bold",
        abcloc="left",
        title="Meetings, clockwise",
        titleweight="normal",
        titlesize=12 if large else 9,
    )
    ax.set_box_aspect(1)
    for spine in ax.spines.values():
        spine.set_visible(False)
    if large:
        labels = {
            "Working papers": PAPER_COLORS["WP"],
            "Information papers": PAPER_COLORS["IP"],
            **INSTRUMENT_COLORS,
            "Reports": REPORT_COLOR,
        }
        handles = [
            Line2D([], [], marker="o", linestyle="none", color=color, label=label)
            for label, color in labels.items()
        ]
        handles.append(
            Line2D(
                [],
                [],
                marker="o",
                linestyle="none",
                markerfacecolor="white",
                markeredgecolor=REPORT_COLOR,
                label="Unresolved reference",
            )
        )
        ax.legend(handles=handles, loc="b", ncols=4, fontsize=10, frame=False)
    return pos, sectors


def radial_figure(data=D, *, layout="sidebar"):
    if layout == "sidebar":
        fig, axes = uplt.subplots(
            [[1, 2], [1, 3]],
            figwidth=7.1,
            figheight=5.1,
            wratios=[1.75, 1],
            ref=2,
            refaspect=1,
            share=False,
            span=False,
            wspace="8em",
            hspace=1.6,
        )
        aspect = 0.68
    else:
        fig, axes = uplt.subplots(
            [[1, 1], [2, 3]],
            figwidth=7.1,
            figheight=7.4,
            ref=2,
            refaspect=1,
            hratios=[2.7, 1],
            share=False,
            span=False,
            hspace=1.6,
        )
        aspect = 0.62
    radial_graph(axes[0], data=data)
    for ax, counts, kind, letter in zip(
        axes[1:], matrices(data), ("paper", "citation"), ("b", "c")
    ):
        composition_bars(
            ax,
            counts,
            kind,
            letter,
            box_aspect=aspect,
            show_xlabel=(kind == "citation" or layout != "sidebar"),
        )
    return fig, axes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", choices=("sidebar", "stacked"), default="sidebar")
    parser.add_argument("--stem", default="breakdown_graph_radial")
    parser.add_argument("--standalone", action="store_true")
    args = parser.parse_args()
    if args.standalone:
        fig, ax = uplt.subplots(figwidth=12, figheight=12, share=False, span=False)
        radial_graph(ax, large=True)
    else:
        fig, axes = radial_figure(layout=args.layout)
    save(fig, args.stem)
    print(
        f"Retained {len(D['nodes'])} nodes, {len(D['edges'])} links; sector order is chronological."
    )


if __name__ == "__main__":
    main()
