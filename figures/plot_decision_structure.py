#!/usr/bin/env python3
"""Historical network, compact connected inset, and instrument citations."""
import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, ConnectionPatch
from plot_graph_radial import D, radial_graph, node_color
from plot_breakdown_profile import uplt, save


def main():
    fig, axes = uplt.subplots([[1, 2], [3, 3]], figwidth=10,
                              hratios=[1, .16], wratios=[1.2, 1], share=False, span=False,
                              wspace="12em", hspace="3em")
    a, b, key = axes
    nodes = {n['id']: n for n in D['nodes']}
    positions, _ = radial_graph(a)
    a.format(title="The historical documentary network", titlesize=10,
             xlim=(-1.48, 1.4), ylim=(-1.48, 1.4))
    centre = 'Measure 15 (2009)'

    # Small selected neighbourhood, not a second full-sized case panel.
    inset = a.inset_axes([0, 0, .40, .40], zoom=False)
    inset.set_box_aspect(1)
    inset.patch.set_visible(False)
    inset.add_patch(Circle((.5, .5), .50, transform=inset.transAxes,
                           facecolor=(1, 1, 1, .93), edgecolor='#727B84',
                           linewidth=.8, clip_on=False, zorder=0))
    target = positions[centre]
    # Connect the circular rim directly to the retained node, without the
    # rectangular bounds and corner connectors of a conventional zoom inset.
    xmin, xmax = a.get_xlim()
    ymin, ymax = a.get_ylim()
    direction = np.array([(target[0] - xmin) / (xmax - xmin) / .40 - .5,
                          (target[1] - ymin) / (ymax - ymin) / .40 - .5])
    distance = np.linalg.norm(direction)
    unit = direction / distance
    perpendicular = np.array([-unit[1], unit[0]])
    tangent_base = .5 + (.25 / distance) * unit
    tangent_offset = .5 * np.sqrt(max(0, 1 - (.5 / distance) ** 2)) * perpendicular
    for rim in (tangent_base + tangent_offset, tangent_base - tangent_offset):
        a.add_artist(ConnectionPatch(xyA=rim, coordsA=inset.transAxes,
                                    xyB=target, coordsB=a.transData,
                                    arrowstyle='-', color='#727B84',
                                    linewidth=.8, clip_on=False, zorder=3))
    a.scatter([target[0]], [target[1]], s=48, facecolors='none',
              edgecolors='#454D55', linewidths=.9, zorder=10)
    layout = {
        'Measure 1 (2004)': (.12, .83),
        centre: (.50, .47),
        'ATCM45:IP 145': (.88, .83),
        'ATCM45:FinalReport': (.50, .08),
    }
    labels = {
        'Measure 1 (2004)': 'Measure 1\n(2004)',
        centre: 'Measure 15\n(2009)',
        'ATCM45:IP 145': 'IP 145\n(2023)',
        'ATCM45:FinalReport': 'Report (2023)',
    }
    styles = {'direct_citation': ('#688FA7', '--'),
              'outcome_text_label': ('#343C4A', '-'),
              'report_body_label': ('#727B84', ':')}
    seen = set()
    for edge in D['edges']:
        source, target = edge['src'], edge['dst']
        identity = source, target, edge['channel']
        if source not in layout or target not in layout or identity in seen:
            continue
        seen.add(identity)
        color, style = styles[edge['channel']]
        inset.plot([layout[source][0], layout[target][0]],
                   [layout[source][1], layout[target][1]],
                   color=color, linestyle=style, lw=.9, zorder=1)
    for identity, (px, py) in layout.items():
        node = nodes[identity]
        marker = {'paper': 's', 'outcome': 'o', 'report': 'D'}[node['kind']]
        inset.scatter([px], [py], s=20, marker=marker, color=node_color(node),
                      edgecolor='white', linewidth=.4, zorder=3)
        inset.text(px, py - .055, labels[identity], ha='center', va='top',
                   fontsize=6.8, linespacing=1.05, zorder=4,
                   bbox=dict(facecolor=(1, 1, 1, .65), edgecolor='none', pad=.3))
    inset.set(xlim=(-.12, 1.12), ylim=(-.16, 1.04))
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_visible(False)
    inset.format(abc=False, grid=False)

    types = ['Recommendation', 'Measure', 'Decision', 'Resolution']
    colors = ['#CC79A7', '#009E73', '#E69F00', '#D55E00']
    counts = np.zeros((4, 4), dtype=int)
    pairs = set()
    for edge in D['edges']:
        source, target = nodes[edge['src']], nodes[edge['dst']]
        pair = edge['src'], edge['dst']
        if (edge['channel'] != 'outcome_text_label' or pair in pairs
                or source['kind'] != 'outcome' or target['kind'] != 'outcome'
                or source.get('placeholder') or target.get('placeholder')):
            continue
        pairs.add(pair)
        counts[types.index(target['outcome_type']), types.index(source['outcome_type'])] += 1
    totals = counts.sum(axis=1)
    shares = np.divide(100 * counts, totals[:, None],
                       out=np.zeros_like(counts, dtype=float), where=totals[:, None] != 0)
    left = np.zeros(4)
    for column, color in enumerate(colors):
        values = shares[:, column]
        b.barh(range(4), values, left=left, width=.57,
               color=color, edgecolor='white', linewidth=.5)
        for row, value in enumerate(values):
            if value >= 12:
                b.text(left[row] + value / 2, row, f'{value:.0f}%',
                        ha='center', va='center', fontsize=9)
        left += values
    b.format(xlim=(0, 100), ylim=(3.6, -.6), xticks=[0, 25, 50, 75, 100],
             yticks=range(4), yticklabels=[f'{label}\n({total:,} pairs)'
                                          for label, total in zip(types, totals)],
             xlabel='Citations made (%)', ylabel='', xgrid=True, ygrid=False,
             abc='a', abcloc='left', abcweight='bold',
             title='Which instruments do later texts cite?', titlesize=10)
    b.set_box_aspect(1)
    for label, color in zip(b.get_yticklabels(), colors):
        label.set_color(color)
    for panel in (a, b):
        panel.set_anchor('N')
        panel.format(abcloc='left', abcweight='bold')
    key.format(abc=False)
    key.set_axis_off()
    document_types = [('Working paper', '#0072B2'), ('Information paper', '#56B4E9'),
                      *zip(types, colors), ('Final report', '#343C4A')]
    handles = [Line2D([], [], marker='o', linestyle='none', color=color,
                       markersize=4, label=label) for label, color in document_types]
    handles += [Line2D([], [], color=color, linestyle=style, lw=3,
                       label=label) for label, (color, style) in zip(
        ['Paper citation', 'Instrument citation', 'Report mention'], styles.values())]
    Axes.legend(key, handles=handles, loc='center', ncols=5, frameon=False,
            fontsize=10.5, columnspacing=1.6, handlelength=1.5, markerscale = 3, linewidth = 8)
    save(fig, 'decision_structure')


if __name__ == '__main__':
    main()
