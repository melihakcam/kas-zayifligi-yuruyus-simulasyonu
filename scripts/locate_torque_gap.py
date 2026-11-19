"""Locate where the activation-rate limits create the right ankle/foot torque gap.

The minimax LP in check_temporal_margin.py has a non-unique primal solution,
so the time profile of one solution is not a reliable location. The dual
multipliers form the certificate of the lower bound: they show which torque
equations (time, joint, direction) and which activation transitions (muscle,
rising/falling) the bound actually depends on.
"""
import json
from pathlib import Path
import sys

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_temporal_margin import margin  # noqa: E402

JOINTS = ['ankle_angle_r', 'subtalar_angle_r', 'mtp_angle_r']
START, END = 1.17, 2.34


def right_foot_contact(model, qpos):
    """Return a boolean stance flag per sample from simulator contacts."""
    data = mujoco.MjData(model)
    bodies = {model.body(name).id for name in ('calcn_r', 'toes_r')}
    stance = np.zeros(len(qpos), dtype=bool)
    for i, q in enumerate(qpos):
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        for c in data.contact[:data.ncon]:
            if model.geom_bodyid[c.geom1] in bodies or model.geom_bodyid[c.geom2] in bodies:
                stance[i] = True
                break
    return stance


def windows(mask, time):
    """Contiguous [start, end] time windows where mask is true."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append([round(float(time[i]), 3), round(float(time[j]), 3)])
            i = j + 1
        else:
            i += 1
    return out


def main():
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'))
    rows = [int(model.jnt_dofadr[model.joint(name).id]) for name in JOINTS]
    summary = json.loads((ROOT / 'results/baseline/summary.json').read_text())
    dt = summary['physics_timestep_s']
    with np.load(ROOT / 'results/baseline/trajectory.npz', allow_pickle=False) as source:
        selected = np.flatnonzero((source['time'] >= START - 1e-9) & (source['time'] <= END + 1e-9))
        time = source['time'][selected]
        active = source['linear_active'][selected][:, rows, :]
        target = (source['torque'][selected] - source['linear_offset'][selected])[:, rows]
        keep = np.any(np.abs(active) > 1e-12, axis=(0, 1))
        active = active[:, :, keep]
        names = source['actuator_names'][keep].tolist()
        tau = source['activation_time_constants'][keep]
        recorded = source['activation'][selected][:, keep]
        qpos = source['qpos'][selected]
    stance = right_foot_contact(model, qpos)
    # The published controller acts every frame_skip physics steps.
    frame_skip = summary['physics_samples'] // summary['control_steps']
    first_index = int(selected[0])
    control_update = ((first_index + np.arange(len(time))) % frame_skip) == 0

    output = ROOT / 'results/torque_gap_location'
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'Dual certificate of the right ankle/foot relaxation, recorded cycle 1.17-2.34 s',
              'interpretation': ('Dual weights show which equations the numerical lower bound rests on. '
                                 'They locate the conflict for this model and recording; they are not a clinical claim.'),
              'joints': JOINTS, 'muscles': names, 'frame_skip': frame_skip,
              'right_foot_stance_windows_s': windows(stance, time),
              'right_foot_swing_windows_s': windows(~stance, time), 'scenarios': []}
    tib = names.index('tibant_r')
    for remaining in (0.6, 0.4):
        scale = np.ones(len(names))
        scale[tib] = remaining
        details = {}
        result = margin(active * scale, target, tau, dt, 1, 1.0, details=details)
        if result['status'] != 'optimal':
            raise RuntimeError(f'LP not verified at {remaining}: {result}')
        steps, dofs, muscles = details['steps'], details['dofs'], details['muscles']
        weights = -details['duals']
        n_bal = steps * dofs
        n_rate = (steps - 1) * muscles
        over = weights[:n_bal].reshape(steps, dofs)          # delivered - target <= s
        under = weights[n_bal:2 * n_bal].reshape(steps, dofs)  # target - delivered <= s
        rising = weights[2 * n_bal:2 * n_bal + n_rate].reshape(steps - 1, muscles)
        falling = weights[2 * n_bal + n_rate:].reshape(steps - 1, muscles)
        balance_total = float(over.sum() + under.sum())
        per_time = over.sum(1) + under.sum(1)
        # Torque direction of the binding equations: under -> needs more positive torque.
        joint_split = {name: {'needs_more_positive_torque': float(under[:, j].sum() / balance_total),
                              'needs_less_positive_torque': float(over[:, j].sum() / balance_total)}
                       for j, name in enumerate(JOINTS)}
        binding = per_time > 1e-6 * per_time.max()
        rate_total = rising.sum() + falling.sum()
        muscle_split = {name: {'rising_limit': float(rising[:, m].sum() / rate_total) if rate_total else 0.0,
                               'falling_limit': float(falling[:, m].sum() / rate_total) if rate_total else 0.0}
                        for m, name in enumerate(names)}
        muscle_split = dict(sorted(muscle_split.items(), key=lambda kv: -sum(kv[1].values())))
        stance_weight = float(per_time[stance].sum() / balance_total)
        near_update = np.zeros(len(time), dtype=bool)
        for k in np.flatnonzero(control_update):
            near_update[max(0, k - 1):k + 2] = True
        entry = {'remaining_active_capacity': remaining,
                 'minimum_max_torque_error_Nm': result['minimum_max_torque_error_Nm'],
                 'balance_dual_sum': balance_total,
                 'binding_torque_windows_s': windows(binding, time),
                 'binding_weight_in_right_stance': stance_weight,
                 'binding_weight_in_right_swing': 1 - stance_weight,
                 'binding_weight_within_1_step_of_control_update': float(per_time[near_update].sum() / balance_total),
                 'share_of_samples_within_1_step_of_control_update': float(near_update.mean()),
                 'joint_direction_split': joint_split,
                 'activation_limit_split': {k: v for k, v in list(muscle_split.items())[:6]},
                 'peak_binding_time_s': float(time[int(np.argmax(per_time))]),
                 'recorded_tibant_activation_at_peak': float(recorded[int(np.argmax(per_time)), tib])}
        report['scenarios'].append(entry)
        np.savez_compressed(output / f'{remaining:.2f}_dual.npz', time=time, over=over, under=under,
                            rising=rising, falling=falling, stance=stance, recorded_activation=recorded,
                            solution_activation=details['solution'], target=target,
                            delivered=details['delivered'])
        print(json.dumps(entry, indent=1), flush=True)
    (output / 'location.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    plot(output, names, tib)


def plot(output, names, tib):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for remaining, color in ((0.6, '#4C78A8'), (0.4, '#E45756')):
        with np.load(output / f'{remaining:.2f}_dual.npz') as d:
            t = d['time']
            w = d['over'].sum(1) + d['under'].sum(1)
            axes[0].plot(t, w / w.sum(), color=color, label=f'%{int(remaining * 100)} kalan kuvvet')
            axes[2].plot(t[:-1], d['rising'][:, tib] + d['falling'][:, tib], color=color)
            stance = d['stance']
            if remaining == 0.4:
                axes[1].plot(t, d['recorded_activation'][:, tib], color='0.3', label='Kayıtlı normal aktivasyon')
                axes[1].plot(t, d['solution_activation'][:, tib], color=color, ls='--', label='Sınırlı çözüm (%40)')
                for ax in axes:
                    ylim = ax.get_ylim()
                    ax.fill_between(t, ylim[0], ylim[1], where=stance, color='0.9', zorder=0, step='mid')
                    ax.set_ylim(ylim)
    axes[0].set_ylabel('Tork denklemi\ndual ağırlığı')
    axes[1].set_ylabel('tibialis anterior\naktivasyonu')
    axes[2].set_ylabel('Aktivasyon hızı\nsınırı ağırlığı')
    axes[2].set_xlabel('Zaman (s) — gri: sağ ayak yerde')
    axes[0].legend(frameon=False)
    axes[1].legend(frameon=False)
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / 'location.png', dpi=150)
    fig.savefig(output / 'location.pdf')


if __name__ == '__main__':
    main()
