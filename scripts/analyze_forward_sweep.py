"""Summarise the forward-simulation sweep and find joint-only failures.

A joint-only failure is a pair whose two single-group weaknesses both walk at
the same capacity while the pair does not.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'results/forward_sweep'
LABELS = {
    'right_tibialis_anterior': 'Tibialis ant.',
    'right_soleus': 'Soleus',
    'right_gastrocnemius': 'Gastroknemius',
    'right_vasti': 'Vastus',
    'right_hamstrings': 'Hamstring',
    'right_gluteus_medius': 'Gluteus med.',
    'right_gluteus_maximus': 'Gluteus max.',
    'right_hip_flexors': 'Kalça fleksör',
}
CODE = {'walked': 0, 'deviated': 1, 'fell': 2}


def main():
    report = json.loads((FOLDER / 'sweep.json').read_text(encoding='utf-8'))
    groups = list(report['groups'])
    rows = report['results']
    levels = sorted({r['remaining_active_capacity'] for r in rows if r['groups']}, reverse=True)
    lookup = {(tuple(sorted(r['groups'])), r['remaining_active_capacity']): r for r in rows}
    joint_only, singles = [], {}
    for level in levels:
        for g in groups:
            singles[(g, level)] = lookup.get(((g,), level))
        for i, a in enumerate(groups):
            for b in groups[i + 1:]:
                pair = lookup.get((tuple(sorted((a, b))), level))
                sa, sb = singles[(a, level)], singles[(b, level)]
                if not (pair and sa and sb):
                    continue
                if sa['outcome'] == 'walked' and sb['outcome'] == 'walked' and pair['outcome'] != 'walked':
                    joint_only.append({'groups': [a, b], 'remaining_active_capacity': level,
                                       'pair_outcome': pair['outcome'],
                                       'pair_first_threshold_crossing_s': pair['first_threshold_crossing_s'],
                                       'pair_max_error_rad': pair['max_mean_coordinate_error_rad'],
                                       'single_max_errors_rad': [sa['max_mean_coordinate_error_rad'],
                                                                 sb['max_mean_coordinate_error_rad']]})
    counts = {}
    for r in rows:
        key = f"{r['remaining_active_capacity']:.1f}|{'pair' if len(r['groups']) == 2 else 'single' if r['groups'] else 'baseline'}"
        counts.setdefault(key, {'walked': 0, 'deviated': 0, 'fell': 0})[r['outcome']] += 1
    summary = {'outcome_counts': counts, 'joint_only_failures': joint_only,
               'baseline': lookup.get(((), 1.0))}
    (FOLDER / 'analysis.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'outcome_counts': counts, 'joint_only_failures': len(joint_only)}, indent=1))
    for j in joint_only:
        print(j)
    plot(groups, levels, lookup)


def plot(groups, levels, lookup):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(['#7fbf7b', '#f6c85f', '#d6604d'])
    n = len(groups)
    fig, axes = plt.subplots(1, len(levels), figsize=(4.2 * len(levels), 5.6), squeeze=False)
    for ax, level in zip(axes[0], levels):
        grid = np.full((n, n), np.nan)
        err = np.full((n, n), np.nan)
        for i, a in enumerate(groups):
            for j, b in enumerate(groups):
                key = (a,) if i == j else tuple(sorted((a, b)))
                r = lookup.get((key, level))
                if r and j <= i:
                    grid[i, j] = CODE[r['outcome']]
                    err[i, j] = r['max_mean_coordinate_error_rad']
        ax.imshow(np.ma.masked_invalid(grid), cmap=cmap, vmin=0, vmax=2)
        for i in range(n):
            for j in range(n):
                if not np.isnan(err[i, j]):
                    ax.text(j, i, f'{err[i, j]:.2f}', ha='center', va='center', fontsize=6.5,
                            fontweight='bold' if i == j else 'normal')
        ax.set_xticks(range(n), [LABELS[g] for g in groups], rotation=60, ha='right', fontsize=7)
        ax.set_yticks(range(n), [LABELS[g] for g in groups], fontsize=7)
        ax.set_title(f'Kalan aktif kuvvet %{int(round(level * 100))}', fontsize=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in cmap.colors]
    fig.legend(handles, ['Yürüdü', 'Hareketten saptı (>0,06 rad)', 'Düştü'],
               loc='lower center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle('Sağ bacak kas zayıflığı — aynı kontrolcüyle ileri simülasyon '
                 '(köşegen: tek grup; hücre: en büyük ort. eklem sapması, rad)', fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(FOLDER / 'sweep.png', dpi=150)
    fig.savefig(FOLDER / 'sweep.pdf')


if __name__ == '__main__':
    main()
