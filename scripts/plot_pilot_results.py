"""Export a standalone scientific pilot figure from validated result files."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'results/temporal_margin'
report = json.loads((folder / 'margin.json').read_text())
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
for rate, label, style in ((None, 'Independent instants', 'o--'),
                           (1.0, 'Activation-rate outer bounds', 's-'),
                           (0.5, 'Half time constants (sensitivity)', '^:')):
    rows = [r for r in report['scenarios'] if r['activation_time_constant_scale'] == rate]
    if any(r['status'] != 'optimal' for r in rows):
        raise ValueError('Only verified optimal results can be plotted')
    axes[0].plot([100*r['remaining_active_capacity'] for r in rows],
                 [r['minimum_max_torque_error_Nm'] for r in rows], style, label=label)
axes[0].set(xlabel='Remaining tibialis anterior capacity (%)', ylabel='Minimum worst torque error (Nm)',
            title='Right ankle/foot relaxation')
axes[0].legend(fontsize=8)
axes[0].grid(alpha=0.2)
with np.load(folder / '0.40_rate_1.0.npz') as data:
    errors = data['delivered_torque'] - data['target_torque']
    x = np.arange(len(errors)) * report['physics_timestep_s']
    for index, name in enumerate(report['joints']):
        axes[1].plot(x, errors[:, index], label=name)
axes[1].set(xlabel='Time from window start (s)', ylabel='Delivered minus target torque (Nm)',
            title='40% capacity: one optimal relaxed solution')
axes[1].legend(fontsize=8)
axes[1].grid(alpha=0.2)
fig.suptitle('Single recorded gait; fixed states; numerical pilot, not a clinical result', fontsize=10)
fig.savefig(folder / 'pilot_results.png', dpi=180)
fig.savefig(folder / 'pilot_results.pdf')
plt.close(fig)
print(folder / 'pilot_results.png')
