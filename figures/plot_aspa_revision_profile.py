#!/usr/bin/env python3
"""Render cached revision dispositions; no source extraction during plotting."""
from pathlib import Path
import hashlib
import json
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/ats-breakdown-mpl")
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.axes import Axes
from plot_breakdown_profile import BLUE, ORANGE, GREY, panel, save, uplt

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / "data/breakdown_profile/aspa_revision_profile.json").read_text())
    for source in data["inputs"]:
        assert hashlib.sha256((ROOT/source["path"]).read_bytes()).hexdigest() == source["sha256"]
    fig, axes = uplt.subplots([[1, 2], [3, 3]], figwidth=10,
                              hratios=[1, .15], refaspect=1, share=False, span=False,
                              wspace="2.1in", hspace="3em")
    a, b, key = axes
    panel(a, "a", "More revisions adopted\ndespite increased disagreement")
    rows = data["annual"]
    xx = np.arange(len(rows), dtype=float)
    xx[5:] += .35
    adopted = np.array([r["adopted"] for r in rows])
    delayed = np.array([r["recorded_non_agreement"] for r in rows])
    a.bar(xx, adopted, width=.64, absolute_width=True, color=BLUE, label="Adopted")
    mask = delayed > 0
    a.bar(xx[mask], delayed[mask], bottom=adopted[mask], width=.64, absolute_width=True,
          color=ORANGE, label="Non-agreement")
    for x, row in zip(xx, rows):
        a.text(x, row["approval_stage_requests"]+.45, str(row["approval_stage_requests"]),
               ha="center", va="bottom", fontsize=8)
        if row["recorded_non_agreement"]:
            a.text(x, row["adopted"] + row["recorded_non_agreement"] / 2,
                   str(row["recorded_non_agreement"]), color="white",
                   ha="center", va="center", fontsize=7.5, fontweight="bold")
    a.axvline(4.65, color="#C4C9CC", lw=.7, ls="--")
    a.format(xlim=(-.6, 9.95), ylim=(0, 28), xticks=xx,
             xticklabels=[str(r["year"]) for r in rows], xrotation=55,
             yticks=[0, 5, 10, 15, 20], xticklabelsize=8,
             xlabel="Meeting year (no meeting in 2020)", ylabel="Protected-area revision requests",
             titlesize=10)
    a.text(2, 27, "47 / 47 adopted\nat the same meeting", ha="center", va="top",
           fontsize=8, color=BLUE)
    a.text(7.35, 27, "65 / 71 adopted\nat the same meeting", ha="center", va="top",
           fontsize=8, color=BLUE)

    panel(b, "b", "Most initially unsuccessful revisions\nsecured agreement")
    labels = ["Litchfield Island\nASPA 113", "Davis Valley / Forlidas Pond\nASPA 119",
              "Cape Crozier\nASPA 124", "Biscoe Point, 2021 revision\nASPA 139",
              "Port Foster\nASPA 145", "Biscoe Point, marine extension\nASPA 139"]
    measures = [5, 7, 9, 14, 10, None]
    for y, row in enumerate(data["delayed_episodes"]):
        end = row["adoption_year"] or row["followup_end"]
        b.plot([row["non_agreement_year"], end], [y, y], color=GREY, lw=1,
               ls="-" if row["adoption_year"] else "--")
        b.scatter([row["non_agreement_year"]], [y], c=ORANGE, marker="x", s=38, lw=1.5, zorder=4)
        if row["adoption_year"]:
            b.scatter([end], [y], c=BLUE, marker="o", s=35, zorder=4)
            b.text(end + .14, y, f"Measure {measures[y]}", ha="left", va="center",
                   color=BLUE, fontsize=8,
                   bbox=dict(facecolor="white", edgecolor="none", pad=1))
        else:
            b.scatter([end], [y], facecolors="white", edgecolors=GREY, marker="s", s=35, zorder=4)
    b.format(xlim=(2020.65, 2025.35), ylim=(5.65, -.65),
             xticks=[2021, 2022, 2023, 2024, 2025], yticks=list(range(6)),
             yticklabels=labels, yticklabelsize=8, xticklabelsize=8,
             xlabel="Year", ylabel="", ygrid=False, xgrid=True,
             gridcolor="#E8EBED", gridlinewidth=.5, titlesize=10,
             yticklen=0)
    handles = [Line2D([], [], color=ORANGE, marker="x", ls="none", label="Non-agreement"),
               Line2D([], [], color=BLUE, marker="o", ls="none", label="Adoption"),
               Line2D([], [], markeredgecolor=GREY, markerfacecolor="white", marker="s", ls="none",
                      label="Unresolved at 2025 cutoff")]
    for ax in (a, b):
        ax.set_anchor("N")
    a.format(ltitle="", title="More revisions adopted\ndespite increased disagreement",
             titleloc="center")
    b.format(ltitle="", title="Most initially unsuccessful revisions\nsecured agreement",
             titleloc="center")
    key.format(abc=False)
    key.set_axis_off()
    Axes.legend(key, handles=handles, frameon=False, loc="center",
                fontsize=8, ncols=3)
    save(fig, "aspa_revision_histories")


if __name__ == "__main__":
    main()
