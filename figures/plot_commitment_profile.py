#!/usr/bin/env python3
"""Plot cached Measure composition and the six outside-class legal histories."""

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ats-breakdown-mpl")
from plot_breakdown_profile import uplt, save
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads(
        (ROOT / "data/breakdown_profile/commitment_profile.json").read_text()
    )
    with uplt.rc.context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
        }
    ):
        fig, axes = uplt.subplots(
            ncols=2, figwidth=7.0, refaspect=1, share=False, span=False
        )
        rows = data["meetings"]
        years = [r["year"] for r in rows]
        bottom = np.zeros(len(rows))
        for name, values, color, hatch in (
            (
                "Protected areas",
                [r["area"] + r["legacy_area"] for r in rows],
                "#4477AA",
                None,
            ),
            ("Historic sites", [r["heritage"] for r in rows], "#BBBBBB", "///"),
            ("Other subjects", [r["other"] for r in rows], "#AA3377", "xx"),
        ):
            axes[0].bar(
                years,
                values,
                bottom=bottom,
                width=0.8,
                color=color,
                edgecolor="#333333",
                linewidth=0.3,
                hatch=hatch,
                label=name,
                absolute_width=True,
            )
            bottom += values
        axes[0].format(
            xlabel="Meeting year",
            ylabel="Adopted Measures",
            ylim=(0, 25),
            xlim=(1994, 2026),
            xticks=[1995, 2005, 2015, 2025],
            yticks=[0, 5, 10, 15, 20, 25],
        )
        axes[0].legend(loc="upper left", frameon=False, fontsize=7, ncols=1)
        for i, case in enumerate(data["cases"]):
            end = int(case["effective_date"][:4]) if case["effective_date"] else 2026
            effective = bool(case["effective_date"])
            color = "#4477AA" if effective else "#AA3377"
            axes[1].plot(
                [case["adoption_year"], end],
                [i, i],
                color=color,
                linestyle="-" if effective else "--",
                linewidth=1.2,
            )
            axes[1].plot(
                case["adoption_year"], i, marker="o", ms=4, color="#333333", mfc="white"
            )
            axes[1].plot(end, i, marker="s" if effective else ">", ms=5, color=color)
        axes[1].format(
            yticks=range(6),
            yticklabels=[c["id"].replace("Measure ", "") for c in data["cases"]],
            ylabel="Measure (number and year)",
            xlabel="Year",
            xlim=(2001, 2028),
            ylim=(5.8, -1.7),
            xticks=[2003, 2009, 2016, 2026],
        )
        axes[1].legend(
            handles=[
                Line2D(
                    [],
                    [],
                    marker="o",
                    color="#333333",
                    mfc="white",
                    linestyle="none",
                    label="Adoption",
                ),
                Line2D(
                    [],
                    [],
                    marker="s",
                    color="#4477AA",
                    linestyle="-",
                    label="Entry into force",
                ),
                Line2D(
                    [],
                    [],
                    marker=">",
                    color="#AA3377",
                    linestyle="--",
                    label="Still pending",
                ),
            ],
            loc="upper left",
            frameon=False,
            fontsize=7,
            ncol=1,
        )
        axes.format(
            abc="a",
            abcloc="left",
            abcweight="bold",
            titleweight="normal",
            ticklabelsize=7,
            grid=False,
        )
        for ax in axes:
            ax.set_box_aspect(1)
        save(fig, "breakdown_commitments")


if __name__ == "__main__":
    main()
