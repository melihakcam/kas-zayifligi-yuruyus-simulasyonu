"""Test whether the right ankle/foot torque gap depends on one controller event.

locate_torque_gap.py places the whole dual weight of the bound at 2.180-2.182 s.
At that control update the published policy switches tibant_r excitation from
about 0.002 to 0.891 and the recorded ankle torque jumps by about 28 Nm in one
2 ms step. This script repeats the bound with that transition removed.
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
EVENT = 2.18


def binding_times(details, time):
    w = -details['duals']
    n = details['steps'] * details['dofs']
    per = (w[:n] + w[n:2 * n]).reshape(details['steps'], details['dofs']).sum(1)
    mask = per > 1e-6 * per.max()
    return [round(float(x), 3) for x in time[mask]], [round(float(x), 4) for x in per[mask] / per.sum()]


def main():
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'))
    rows = [int(model.jnt_dofadr[model.joint(n).id]) for n in JOINTS]
    with np.load(ROOT / 'results/baseline/trajectory.npz', allow_pickle=False) as s:
        sel = np.flatnonzero((s['time'] >= 1.17 - 1e-9) & (s['time'] <= 2.34 + 1e-9))
        t = s['time'][sel]
        A = s['linear_active'][sel][:, rows, :]
        T = (s['torque'][sel] - s['linear_offset'][sel])[:, rows]
        keep = np.any(np.abs(A) > 1e-12, axis=(0, 1))
        A = A[:, :, keep]
        names = s['actuator_names'][keep].tolist()
        tau = s['activation_time_constants'][keep]
        all_names = list(s['actuator_names'])
        ctrl = s['ctrl'][sel][:, all_names.index('tibant_r')]
        act = s['activation'][sel][:, all_names.index('tibant_r')]
    k = int(np.argmin(np.abs(t - EVENT)))
    jumps = np.abs(np.diff(T[:, 0]))
    tib = names.index('tibant_r')
    report = {
        'scope': 'Right ankle/foot relaxation, recorded cycle 1.17-2.34 s, activation time constant scale 1.0',
        'event': {
            'time_s': [round(float(t[k]), 3), round(float(t[k + 1]), 3)],
            'tibant_r_excitation': [float(ctrl[k - 1]), float(ctrl[k])],
            'tibant_r_activation': [float(act[k]), float(act[k + 1])],
            'ankle_target_torque_Nm': [float(T[k, 0]), float(T[k + 1, 0])],
            'ankle_target_jump_Nm': float(T[k + 1, 0] - T[k, 0]),
            'median_ankle_target_step_Nm': float(np.median(jumps)),
            'large_tibant_excitation_changes': [
                {'time_s': round(float(t[i + 1]), 3), 'change': float(np.diff(ctrl)[i])}
                for i in np.flatnonzero(np.abs(np.diff(ctrl)) > 0.3)],
        },
        'scenarios': [],
        'interpretation': ('If the bound vanishes or shrinks sharply when one transition is removed, '
                           'the bound reflects a single controller-induced torque step, not a sustained '
                           'property of the gait cycle.'),
    }
    before, after = slice(0, k), slice(k + 2, None)
    for remaining in (0.8, 0.6, 0.5, 0.4):
        scale = np.ones(len(names))
        scale[tib] = remaining
        Aw = A * scale
        full = margin(Aw, T, tau, 0.002, 1, 1.0)
        d1, d2 = {}, {}
        r1 = margin(Aw[before], T[before], tau, 0.002, 1, 1.0, details=d1)
        r2 = margin(Aw[after], T[after], tau, 0.002, 1, 1.0, details=d2)
        entry = {'remaining_active_capacity': remaining,
                 'full_cycle_bound_Nm': full.get('minimum_max_torque_error_Nm'),
                 'before_event_bound_Nm': r1.get('minimum_max_torque_error_Nm'),
                 'after_event_bound_Nm': r2.get('minimum_max_torque_error_Nm'),
                 'statuses': [full['status'], r1['status'], r2['status']]}
        if r2.get('minimum_max_torque_error_Nm', 0) > 1e-9:
            entry['after_event_binding_times_s'], entry['after_event_binding_weights'] = binding_times(d2, t[after])
        report['scenarios'].append(entry)
        print(entry, flush=True)
    out = ROOT / 'results/torque_gap_location'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'event_check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
