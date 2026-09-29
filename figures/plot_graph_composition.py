#!/usr/bin/env python3
"""Conditional link composition for the opening figure.

The bars retain the original heatmaps' row denominators. They describe the
types of recovered links, not proposal success or transition probabilities.
No links are pooled or recomputed by this display helper.
"""

import numpy as np

from plot_graph_opening import (
    D,
    OUTCOMES,
    PAPERS,
    SHORT,
    annotation_color,
    matrices,
    row_proportions,
)
from plot_breakdown_profile import ROOT, uplt

PAPER_COLORS = {"WP": "#0072B2", "IP": "#56B4E9"}
INSTRUMENT_COLORS = {
    "Recommendation": "#CC79A7",
    "Measure": "#009E73",
    "Decision": "#E69F00",
    "Resolution": "#D55E00",
}
# A combined mapping lets the graph and the bars use identical categories.
CATEGORY_COLORS = {**PAPER_COLORS, **INSTRUMENT_COLORS}
LABEL_MIN_PERCENT = 14.0
TEXT_COLOR = "#172C38"


def composition_data(counts, kind):
    """Validate a four-row link matrix, returning exact display percentages."""
    if kind not in ("paper", "citation"):
        raise ValueError("kind must be 'paper' or 'citation'")
    counts = np.asarray(counts, dtype=float)
    expected = (4, 2 if kind == "paper" else 4)
    if counts.shape != expected:
        raise ValueError(f"Expected a {expected} count matrix for {kind} links")
    values = row_proportions(counts) * 100
    return values, counts.sum(axis=1)


def composition_bars(ax, counts, kind, letter, *, box_aspect=1, show_xlabel=True):
    """Draw row-conditional 100% bars and return percentages and row totals.

    ``kind='paper'`` has outcome rows and linked paper-type columns;
    ``kind='citation'`` has citing rows and cited instrument-type columns.
    Empty rows remain undefined, not artificial all-zero probabilities.
    Labels round display values only; bar widths retain exact proportions.
    A caller may tune ``box_aspect`` to fit the surrounding figure layout and
    suppress a repeated x-axis label with ``show_xlabel=False``.
    """
    values, totals = composition_data(counts, kind)
    categories = PAPERS if kind == "paper" else OUTCOMES
    colors = PAPER_COLORS if kind == "paper" else INSTRUMENT_COLORS
    labels = ("Working", "Information") if kind == "paper" else SHORT
    title = "Paper–outcome links" if kind == "paper" else "Instrument citations"
    if len(letter) != 1 or not letter.islower() or not letter.isalpha():
        raise ValueError("Panel labels must be single lowercase letters")
    if box_aspect is not None:
        ax.set_box_aspect(box_aspect)

    y = np.arange(4)
    left = np.zeros(4)
    handles = []
    for column, category in enumerate(categories):
        widths = np.nan_to_num(values[:, column], nan=0.0)
        bars = ax.barh(
            y,
            widths,
            left=left,
            width=0.62,
            color=colors[category],
            edgecolor="white",
            linewidth=0.8,
            label=labels[column],
            zorder=3,
        )
        handles.append(bars)
        for row, width in enumerate(widths):
            if width >= LABEL_MIN_PERCENT:
                ax.text(
                    left[row] + width / 2,
                    row,
                    f"{width:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=annotation_color(colors[category]),
                    zorder=4,
                )
        left += widths

    for row in np.flatnonzero(totals == 0):
        ax.text(
            50, row, "No links", ha="center", va="center", fontsize=8, color=TEXT_COLOR
        )

    # Explicit strings allow standalone proofs to retain their b/c labels.
    panel_letters = [""] * ax.number
    panel_letters[-1] = letter
    ax.format(
        title=title,
        titleloc="left",
        titleweight="normal",
        titlesize=9,
        abc=panel_letters,
        abcloc="left",
        abcweight="bold",
        abcsize=11,
        xlim=(0, 100),
        ylim=(3.65, -0.65),
        xticks=[0, 50, 100],
        xticklabels=["0", "50", "100%"],
        yticks=y,
        yticklabels=[f"{name} ({int(total):,})" for name, total in zip(SHORT, totals)],
        xlabel="Share of links in each row" if show_xlabel else "",
        ylabel="",
        xgrid=True,
        ygrid=False,
        gridcolor="#E5EAED",
        gridlinewidth=0.55,
        xticklen=2.5,
        yticklen=0,
        xticklabelsize=8,
        yticklabelsize=8,
        ytickloc="left",
        yticklabelloc="left",
        xminorlocator="null",
        yminorlocator="null",
    )
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.legend(
        handles=handles,
        labels=list(labels),
        loc="b",
        ncols=2,
        frame=False,
        fontsize=7.5,
        handlelength=1.2,
        handleheight=0.9,
        columnspacing=1.1,
        borderaxespad=0,
        pad=0.35,
        space="3.7em",
    )
    return values, totals


def component_preview():
    """Build an independent proof without overwriting the manuscript figure."""
    fig, axes = uplt.subplots(
        nrows=2, figwidth=3.55, share=False, span=False, hspace=1.7
    )
    for ax, counts, kind, letter in zip(
        axes, matrices(D), ("paper", "citation"), ("b", "c")
    ):
        composition_bars(ax, counts, kind, letter, box_aspect=0.76)
    return fig, axes


if __name__ == "__main__":
    fig, axes = component_preview()
    for suffix in ("png", "pdf"):
        fig.save(
            ROOT / f"figures/graph_composition_preview.{suffix}",
            facecolor="white",
            dpi=250,
        )
    uplt.close(fig)
