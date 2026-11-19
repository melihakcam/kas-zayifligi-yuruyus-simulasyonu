"""Construct sufficient fixed-trajectory feasibility witnesses at every physics step.

Tangents restrict (rather than relax) the exact Euler muscle reachable interval.
A failed LP is inconclusive. A successful LP is checked against native MuJoCo.
Source: MuJoCo 3.17.0 engine_util_misc.c, mju_muscleDynamics.
"""
import argparse
from itertools import combinations
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy import sparse
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'right_vasti': ['vasint_r', 'vaslat_r', 'vasmed_r'],
    'right_hamstrings': ['bflh_r', 'semimem_r', 'semiten_r'],
    'right_soleus': ['soleus_r'],
    'right_gastrocnemius': ['gasmed_r', 'gaslat_r'],
    'right_tibialis_anterior': ['tibant_r'],
}


def endpoints(a, tau, dt):
    factor = 0.5 + 1.5 * a
    upper = a + dt * (1 - a) / (tau[:, 0] * factor)
    lower = a - dt * a * factor / tau[:, 1]
    upper_derivative = 1 - 2 * dt / (tau[:, 0] * factor**2)
    lower_derivative = 1 - dt * (0.5 + 3 * a) / tau[:, 1]
    return lower, upper, lower_derivative, upper_derivative


def native_check(activation, tau, dt):
    a = activation[:-1]
    delta = (activation[1:] - a) / dt
    factor = 0.5 + 1.5 * a
    time_constant = np.where(delta > 0, tau[:, 0] * factor, tau[:, 1] / factor)
    controls = a + delta * time_constant
    control_violation = float(max(0, -controls.min(), controls.max() - 1))
    controls = np.clip(controls, 0, 1)
    native = np.array([mujoco.mju_muscleDynamics(float(u), float(x), prm)
                       for u, x, prm in zip(controls.ravel(), a.ravel(),
                                           np.tile(tau, (len(a), 1)))])
    error = float(np.max(np.abs(a + dt * native.reshape(a.shape) - activation[1:])))
    return controls, control_violation, error


def sufficient_lp(active, target, center, tau, dt):
    steps, _, muscles = active.shape
    balance = sparse.block_diag([sparse.csr_matrix(a) for a in active], format='csr')
    used_rows = np.asarray(abs(balance).sum(axis=1)).ravel() > 1e-12
    if np.any(np.abs(target.ravel()[~used_rows]) > 1e-5):
        return {'status': 'not_certified', 'reason': 'fixed muscles leave unmatched torque'}, None, None
    balance = balance[used_rows]
    target_flat = target.ravel()[used_rows]
    # Scale each torque row to reduce conditioning differences between joints.
    row_scale = np.maximum(np.asarray(abs(balance).max(axis=1).toarray()).ravel(), 1e-12)
    scaled_balance = balance.multiply((1 / row_scale)[:, None]).tocsr()
    lower, upper, dlower, dupper = endpoints(center[:-1], tau, dt)
    n = (steps - 1) * muscles
    current = sparse.coo_matrix((np.ones(n), (np.arange(n), np.arange(n))),
                                shape=(n, steps * muscles)).tocsr()
    following = sparse.coo_matrix((np.ones(n), (np.arange(n), np.arange(n) + muscles)),
                                  shape=(n, steps * muscles)).tocsr()
    # F_upper is convex, so its tangent is a global lower bound. F_lower is
    # concave, so its tangent is a global upper bound. These constraints are
    # sufficient for the true reachable interval, although not necessary.
    inequality = sparse.vstack((following - current.multiply(dupper.ravel()[:, None]),
                                current.multiply(dlower.ravel()[:, None]) - following), format='csr')
    rhs = np.concatenate(((upper - dupper * center[:-1]).ravel(),
                          (dlower * center[:-1] - lower).ravel()))
    result = linprog(np.zeros(steps * muscles), A_eq=scaled_balance, b_eq=target_flat / row_scale,
                     A_ub=inequality, b_ub=rhs, bounds=(0, 1), method='highs-ipm',
                     options={'time_limit': 45})
    if not result.success:
        return {'status': 'not_certified', 'solver_status': int(result.status)}, None, None
    activation = result.x.reshape(steps, muscles)
    controls, violation, error = native_check(activation, tau, dt)
    torque_error = float(np.max(np.abs(balance @ result.x - target_flat)))
    good = torque_error <= 1e-5 and violation <= 1e-6 and error <= 1e-7
    return {'status': 'certified_fixed_trajectory' if good else 'verification_failed',
            'max_torque_error': torque_error, 'max_excitation_bound_violation': violation,
            'max_native_activation_step_error': error}, activation, controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=float, default=1.17)
    parser.add_argument('--duration', type=float, default=1.17)
    parser.add_argument('--remaining', type=float, nargs='+', default=[0.8, 0.6, 0.4])
    parser.add_argument('--pairs', action='store_true', help='Include all pairwise losses')
    args = parser.parse_args()
    if args.start < 0 or args.duration <= 0 or any(not 0 < x <= 1 for x in args.remaining):
        parser.error('Invalid analysis window or capacity')
    folder = ROOT / 'results/baseline'
    summary = json.loads((folder / 'summary.json').read_text())
    if not summary['completed_requested_cycles'] or summary['integrator_id'] != 0:
        raise ValueError('Completed Euler baseline required')
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'))
    if np.any(model.actuator_dynprm[:, 2] != 0) or np.any(model.actuator_actearly):
        raise ValueError('This certificate requires hard-switching muscles without actearly')
    if np.any(model.actuator_dyntype != mujoco.mjtDyn.mjDYN_MUSCLE):
        raise ValueError('Only muscle activation dynamics supported')
    with np.load(folder / 'trajectory.npz', allow_pickle=False) as source:
        times = source['time']
        indices = np.flatnonzero((times >= args.start - 1e-9) &
                                 (times <= args.start + args.duration + 1e-9))
        if len(indices) < 2 or np.any(np.diff(indices) != 1):
            raise ValueError('Consecutive physics samples required')
        active = source['linear_active'][indices]
        target = source['torque'][indices] - source['linear_offset'][indices]
        witness = source['activation'][indices]
        original_controls = source['ctrl'][indices[:-1]]
        names = source['actuator_names'].tolist()
        tau = model.actuator_dynprm[:, :3].copy()
        if names != [model.actuator(i).name for i in range(model.nu)]:
            raise ValueError('Actuator ordering mismatch')
        if not np.array_equal(tau[:, :2], source['activation_time_constants']):
            raise ValueError('Activation parameter mismatch')
        selected_times = times[indices]
    dt = summary['physics_timestep_s']
    if np.max(np.abs(np.diff(selected_times) - dt)) > 1e-9:
        raise ValueError('Physics step mismatch')
    _, violation, error = native_check(witness, tau, dt)
    native_original = np.array([mujoco.mju_muscleDynamics(float(u), float(a), prm)
                               for u, a, prm in zip(original_controls.ravel(), witness[:-1].ravel(),
                                                   np.tile(tau, (len(witness) - 1, 1)))])
    original_error = float(np.max(np.abs(witness[:-1] + dt * native_original.reshape(witness[:-1].shape)
                                        - witness[1:])))
    if violation > 1e-7 or error > 1e-9 or original_error > 1e-9:
        raise ValueError(f'Baseline activation validation failed: {violation}, {error}, {original_error}')
    group_indices = {key: [names.index(name) for name in members] for key, members in GROUPS.items()}
    free = np.array([i for i, name in enumerate(names) if name.endswith('_r') and not name.startswith('Ps_')])
    fixed = np.array([i for i in range(len(names)) if i not in free])
    fixed_torque = np.einsum('tjm,tm->tj', active[:, :, fixed], witness[:, fixed])
    output = ROOT / 'results/activation_validation'
    output.mkdir(parents=True, exist_ok=True)
    report = {
        'scope': 'Fixed recorded states, active capacity scaled, passive forces unchanged; free initial activation; open horizon',
        'interpretation': 'Certified cases have verified native Euler activation witnesses. Not-certified cases are inconclusive.',
        'source': 'https://github.com/google-deepmind/mujoco/blob/3.17.0/src/engine/engine_util_misc.c',
        'sample_count': len(indices), 'first_time_s': float(selected_times[0]),
        'last_time_s': float(selected_times[-1]), 'physics_timestep_s': dt,
        'baseline_original_control_step_error': original_error, 'groups': GROUPS, 'scenarios': [],
        'compensation_scope': '39 right-leg muscles optimized; all other activations fixed to baseline',
    }
    scenarios = [()] + [(key,) for key in GROUPS]
    if args.pairs:
        scenarios += list(combinations(GROUPS, 2))
    prior = {}
    prior_path = output / 'validation.json'
    if prior_path.exists():
        old = json.loads(prior_path.read_text())
        if (old.get('first_time_s') == report['first_time_s'] and
                old.get('last_time_s') == report['last_time_s'] and
                old.get('physics_timestep_s') == dt):
            for entry in old.get('scenarios', []):
                if entry['status'] == 'certified_fixed_trajectory':
                    prior[(entry['remaining_active_capacity'], tuple(entry['groups']))] = entry
    for remaining in args.remaining:
        for scenario in scenarios:
            if not scenario and remaining != args.remaining[0]:
                continue
            scale = np.ones(len(names))
            for group in scenario:
                scale[group_indices[group]] = remaining
            # Scaling the recorded activations is an inexpensive exact torque
            # witness when its activation and excitation bounds still hold.
            direct = witness / scale
            direct_valid = bool(np.max(direct) <= 1 + 1e-9)
            if direct_valid:
                _, direct_violation, direct_error = native_check(direct, tau, dt)
                direct_valid = direct_violation <= 1e-6 and direct_error <= 1e-7
            previous = prior.get((remaining, tuple(scenario)))
            if previous is not None:
                with np.load(output / previous['witness_file'], allow_pickle=False) as saved:
                    activation = saved['activation'].copy()
                record = {'status': 'certified_fixed_trajectory', 'construction': 'rechecked_saved_witness'}
            elif direct_valid:
                record = {'status': 'certified_fixed_trajectory', 'construction': 'rescaled_recorded_activation'}
                activation = direct
            elif scenario:
                record, partial, _ = sufficient_lp(active[:, :, free] * scale[free], target - fixed_torque,
                                                    witness[:, free], tau[free], dt)
                activation = witness.copy() if partial is not None else None
                if activation is not None:
                    activation[:, free] = partial
            else:
                record = {'status': 'certified_fixed_trajectory'}
                activation = witness.copy()
            controls = None
            if activation is not None:
                controls, violation, error = native_check(activation, tau, dt)
                torque_error = float(np.max(np.abs(np.einsum('tjm,tm->tj', active * scale, activation) - target)))
                record.update(max_torque_error=torque_error, max_excitation_bound_violation=violation,
                              max_native_activation_step_error=error)
                if torque_error > 1e-5 or violation > 1e-6 or error > 1e-7:
                    record['status'] = 'verification_failed'
            record.update(remaining_active_capacity=remaining, groups=list(scenario))
            if record['status'] == 'certified_fixed_trajectory':
                name = f'{remaining:.2f}_' + ('+'.join(scenario) or 'baseline') + '.npz'
                np.savez_compressed(output / name, time=selected_times, activation=activation,
                                    excitation=controls, actuator_names=np.asarray(names), scale=scale)
                record['witness_file'] = name
            report['scenarios'].append(record)
            (output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(remaining, '+'.join(scenario) or 'baseline', record['status'], flush=True)


if __name__ == '__main__':
    main()
