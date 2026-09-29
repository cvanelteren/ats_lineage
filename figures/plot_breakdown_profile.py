#!/usr/bin/env python3
"""Plot the cached decision profile; no episode computation during rendering."""

from pathlib import Path
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ats-breakdown-mpl")
import matplotlib

matplotlib.use("Agg")
import ultraplot as uplt
from matplotlib.ticker import PercentFormatter, MaxNLocator
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data/breakdown_profile/profile.json").read_text())
BLUE, ORANGE, TEAL, GREY = "#27628C", "#C36B32", "#287D74", "#727B84"
uplt.rc.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#8A9197",
        "axes.linewidth": 0.6,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.dpi": 450,
        "abc": "a",
        "abc.loc": "left",
        "abc.size": 11,
        "abc.weight": "bold",
        "abc.border": False,
        "title.weight": "normal",
        "title.border": False,
        "axes.grid": False,
        "axes.axisbelow": True,
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
    }
)


def panel(ax, letter, title=None):
    ax.set_box_aspect(1)
    assert letter == chr(ord("a") + ax.number - 1)
    ax.format(
        abc="a",
        abcloc="left",
        abcweight="bold",
        title=title or "",
        titleweight="normal",
        ygrid=True,
        xgrid=False,
        gridcolor="#E8EBED",
        gridlinewidth=0.5,
    )


def save(fig, name):
    for extension in ("pdf", "svg", "png"):
        fig.save(ROOT / f"figures/{name}.{extension}", facecolor="white")
    uplt.close(fig)


def overview():
    fig, axes = uplt.subplots(
        nrows=2, ncols=2, figwidth=7.1, refaspect=1, share=False, span=False
    )
    a, b, c, d = axes
    panel(a, "a")
    years = [r["year"] for r in D["annual"]]
    values = [r["official_outputs"] for r in D["annual"]]
    a.plot(years, values, color=BLUE, lw=1, marker="o", ms=2.5)
    a.format(
        xlim=(1959, 2028),
        ylim=(0, 45),
        xlabel="Regular meeting year",
        ylabel="Adopted instruments per meeting",
        xticks=[1961, 1980, 2000, 2025],
    )
    panel(b, "b")
    cohorts = [
        r
        for r in D["episodes"]["outcome_blind_K10"]["cohorts"]
        if r["decade"] in (2000, 2010)
    ]
    b.bar([0, 1], [r["rate"] for r in cohorts], color=[BLUE, ORANGE], width=0.52)
    for i, r in enumerate(cohorts):
        b.text(
            i,
            r["rate"] + 0.025,
            f'{r["rate"]:.1%}',
            ha="center",
            va="bottom",
            fontsize=8,
        )
    b.format(
        ylim=(0, 0.60),
        xticks=[0, 1],
        xticklabels=["2000–2009", "2010–2014"],
        xlabel="First paper's year",
        ylabel="Groups with a matching outcome title",
        yformatter=PercentFormatter(1, decimals=0),
    )
    panel(c, "c")
    n = D["graph"]["n_resolutions"]
    counts = [D["graph"]["direct_measure"], D["graph"]["eventual_measure"]]
    c.bar([0, 1], [x / n for x in counts], color=[GREY, TEAL], width=0.52)
    for i, value in enumerate(counts):
        c.text(i, value / n + 0.02, f"{value}/{n}", ha="center")
    c.format(
        ylim=(0, 0.45),
        xticks=[0, 1],
        xticklabels=["Direct link", "With intervening\ninstruments"],
        xlabel="Resolution → later Measure",
        ylabel="Share of Resolutions in the graph",
        yformatter=PercentFormatter(1, decimals=0),
    )
    panel(d, "d")
    d.bar([0, 1, 2], [7, 3, 0], color=[TEAL, GREY, ORANGE], width=0.52)
    for i, value in enumerate([7, 3, 0]):
        d.text(i, value + 0.2, str(value), ha="center")
    d.format(
        ylim=(0, 9),
        xticks=[0, 1, 2],
        xticklabels=["Plans\nretained", "Working\npapers", "New\nMeasures"],
        ylabel="Count in the documented 2019 case",
        ylocator=MaxNLocator(integer=True),
    )
    save(fig, "breakdown_overview")


def episodes():
    fig, axes = uplt.subplots(
        ncols=2, figwidth=7.1, refaspect=1, share=False, span=False
    )
    for ax, k, letter in zip(axes, (5, 10), "ab"):
        panel(ax, letter, f"{k}-meeting follow-up")
        for spec, color, marker, label in [
            ("outcome_blind", BLUE, "o", "Grouped by paper titles"),
            ("shared_outcome", ORANGE, "s", "Also grouped by outcome"),
        ]:
            rows = D["episodes"][f"{spec}_K{k}"]["cohorts"]
            x = np.arange(len(rows))
            ax.plot(
                x,
                [r["rate"] for r in rows],
                color=color,
                marker=marker,
                ms=4,
                lw=1.1,
                label=label,
            )
            if spec == "outcome_blind":
                labels = [f'{r["decade"]}\n–{r["last_year"]}' for r in rows]
        ax.format(
            ylim=(0, 0.60),
            xlim=(-0.3, 5.3),
            xticks=x,
            xticklabels=labels,
            xlabel="First paper's year",
            ylabel="Groups with a matching outcome title",
            yformatter=PercentFormatter(1, decimals=0),
            xticklabelsize=7,
        )
        ax.legend(frameon=False, fontsize=7, loc="upper left", ncols=1)
    save(fig, "breakdown_episode_sensitivity")


def evidence():
    fig, axes = uplt.subplots(
        ncols=2, figwidth=7.1, refaspect=1, share=False, span=False
    )
    a, b = axes
    panel(a, "a")
    rows = D["graph"]["fixed_horizons"]
    xx = [int(k) for k in rows]
    yy = [r["rate"] for r in rows.values()]
    a.scatter(xx, yy, color=TEAL, marker="o", s=24)
    for x, y, r in zip(xx, yy, rows.values()):
        a.annotate(
            f'{r["eventual_measure"]}/{r["eligible"]}',
            (x, y),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    a.format(
        ylim=(0, 0.35),
        xlim=(0, 11),
        xticks=xx,
        xlabel="Follow-up (meeting units)",
        ylabel="Resolutions linked to a later Measure",
        yformatter=PercentFormatter(1, decimals=0),
    )
    panel(b, "b")
    counts = D["audit"]["relationships"]
    labels = ["Mentions", "Unrelated", "Implements", "Develops"]
    values = [
        counts.get(k, 0) for k in ["mentions", "unrelated", "implements", "develops"]
    ]
    b.bar(range(4), values, color=[GREY, GREY, TEAL, BLUE], width=0.55)
    for i, v in enumerate(values):
        b.text(i, v + 0.3, str(v), ha="center")
    b.format(
        ylim=(0, 14),
        xticks=range(4),
        xticklabels=labels,
        ylabel="Cases in the selected 21-case check",
        xrotation=25,
        xticklabelsize=7,
        ylocator=MaxNLocator(integer=True),
    )
    save(fig, "breakdown_evidence_audit")


if __name__ == "__main__":
    overview()
    episodes()
    evidence()
    print("Wrote three figures as PDF, SVG and 450 dpi PNG.")
