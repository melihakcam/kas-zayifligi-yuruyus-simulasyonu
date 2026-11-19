"""Screen fixed-state torque feasibility with an optimistic muscle-rate envelope.

Envelope feasibility is a necessary condition, not a physiological solution.
Only an envelope-infeasible case can eliminate the corresponding rate-limited model.
"""

import argparse
import csv
from itertools import combinations
import json
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]


def feasibility(active, target, envelope=None):
    steps, dofs, muscles = active.shape
    balance = sparse.block_diag([sparse.csr_matrix(matrix) for matrix in active], format='csr')
    inequality = None
    limits = None
    if envelope is not None:
        up, down = envelope
        forward = sparse.diags([np.ones(steps - 1)], [1], shape=(steps - 1, steps), format='csr')
        current = sparse.diags([np.ones(steps - 1)], [0], shape=(steps - 1, steps), format='csr')
        increase = sparse.kron(forward, sparse.eye(muscles)) - sparse.kron(current, sparse.diags(up))
        decrease = sparse.kron(current, sparse.diags(down)) - sparse.kron(forward, sparse.eye(muscles))
        inequality = sparse.vstack((increase, decrease), format='csr')
        limits = np.concatenate((np.tile(1.0 - up, steps - 1), np.zeros((steps - 1) * muscles)))
    result = linprog(np.zeros(steps * muscles), A_eq=balance, b_eq=target.ravel(),
                     A_ub=inequality, b_ub=limits, bounds=(0.0, 1.0), method='highs',
                     options={'time_limit': 60})
    if result.status not in (0, 2):
        return {'status': 'unresolved', 'solver_status': int(result.status), 'message': result.message}
    if result.success:
        residual = float(np.max(np.abs(balance @ result.x - target.ravel())))
        violation = float(max(0.0, np.max(inequality @ result.x - limits))) if envelope is not None else 0.0
        if residual > 1e-5 or violation > 1e-7:
            return {'status': 'unresolved', 'torque_residual': residual, 'inequality_violation': violation}
        return {'status': 'feasible', 'max_torque_residual': residual}
    return {'status': 'infeasible', 'solver_status': 2}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stride', type=int, default=10)
    parser.add_argument('--start', type=float, default=1.2)
    parser.add_argument('--duration', type=float, default=1.0)
    parser.add_argument('--remaining', type=float, nargs='+', default=[0.8, 0.6])
    parser.add_argument('--output', default='results/weakness_screen')
    parser.add_argument('--scenario', nargs='+', help='Only named groups, joined by + for pairs; baseline is always included')
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must remain inside the D drive project')
    if args.stride < 1 or args.duration <= 0 or any(not 0 < value <= 1 for value in args.remaining):
        parser.error('Invalid stride, duration or remaining force fraction')
    baseline = ROOT / 'results/baseline'
    summary = json.loads((baseline / 'summary.json').read_text())
    if not summary['completed_requested_cycles']:
        raise RuntimeError('The baseline horizon must complete before weakness screening')
    if summary['integrator_id'] != 0 or summary['activation_dynamics'] != ['mjDYN_MUSCLE']:
        raise ValueError('The screening envelope requires Euler muscle activation dynamics')
    with np.load(baseline / 'trajectory.npz', allow_pickle=False) as source:
        indices = np.flatnonzero((source['time'] >= args.start) &
                                 (source['time'] < args.start + args.duration))[::args.stride]
        if len(indices) < 2:
            raise ValueError('Not enough baseline samples')
        active = source['linear_active'][indices]
        target = source['torque'][indices] - source['linear_offset'][indices]
        tau = source['activation_time_constants'].copy()
        names = source['actuator_names'].tolist()
        witness = source['activation'][indices]
    timestep = summary['physics_timestep_s']
    # For MuJoCo muscle dynamics on 0<=a,u<=1, the maximal speed is bounded by
    # 2*(1-a)/tau_act upward and 2*a/tau_deact downward. Repeated Euler bounds
    # give a linear, optimistic reachable envelope across the sampling interval.
    if np.any(tau <= 0):
        raise ValueError('Positive activation and deactivation constants required')
    if np.any(2 * timestep > tau):
        raise ValueError('Timestep too large for the repeated linear envelope')
    up = np.maximum(0.0, 1.0 - 2.0 * timestep / tau[:, 0]) ** args.stride
    down = np.maximum(0.0, 1.0 - 2.0 * timestep / tau[:, 1]) ** args.stride
    witness_error = float(np.max(np.abs(np.einsum('tjm,tm->tj', active, witness) - target)))
    witness_violation = float(max(0.0, np.max(witness[1:] - up * witness[:-1] - (1 - up)),
                                  np.max(down * witness[:-1] - witness[1:])))
    if witness_error > 1e-5 or witness_violation > 1e-6:
        raise RuntimeError(f'Baseline witness check failed: {witness_error}, {witness_violation}')
    groups = {
        'right_vasti': ['vasint_r', 'vaslat_r', 'vasmed_r'],
        'right_hamstrings': ['bflh_r', 'semimem_r', 'semiten_r'],
        'right_soleus': ['soleus_r'],
        'right_gastrocnemius': ['gasmed_r', 'gaslat_r'],
        'right_tibialis_anterior': ['tibant_r'],
    }
    group_indices = {key: [names.index(name) for name in members] for key, members in groups.items()}
    scenarios = [()] + [(key,) for key in groups] + list(combinations(groups, 2))
    if args.scenario:
        requested = [tuple(value.split('+')) for value in args.scenario]
        if any(key not in groups for scenario in requested for key in scenario):
            parser.error('Unknown anatomical group')
        scenarios = [()] + requested
    records = []
    for remaining in args.remaining:
        for scenario in scenarios:
            scale = np.ones(active.shape[-1])
            for group in scenario:
                scale[group_indices[group]] = remaining
            matrix = active * scale[None, None, :]
            if not scenario:
                independent = {'status': 'feasible', 'construction': 'recorded_baseline_witness',
                               'max_torque_residual': witness_error}
                envelope = {'status': 'feasible', 'construction': 'recorded_baseline_witness',
                            'max_torque_residual': witness_error}
            else:
                independent = feasibility(matrix, target)
                envelope = feasibility(matrix, target, (up, down)) if independent['status'] == 'feasible' else {'status': 'not_evaluated'}
            record = {'remaining_active_capacity': remaining, 'groups': list(scenario),
                      'independent': independent, 'optimistic_envelope': envelope}
            records.append(record)
            print(remaining, '+'.join(scenario) or 'baseline', independent['status'], envelope['status'], flush=True)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        'scope': 'fixed sampled baseline torque; active capacity scaled; passive force unchanged',
        'physiological_dynamic_feasibility_proven': False,
        'envelope': 'optimistic necessary bounds, free initial activation, open horizon',
        'window_start_s': args.start, 'window_duration_s': args.duration, 'sample_count': len(indices),
        'physics_timestep_s': timestep, 'stride': args.stride,
        'baseline_witness_torque_error': witness_error, 'baseline_witness_envelope_violation': witness_violation,
        'groups': groups, 'scenarios': records,
    }
    (output / 'screen.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (output / 'screen.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['remaining_active_capacity', 'groups', 'independent', 'optimistic_envelope'])
        for record in records:
            writer.writerow([record['remaining_active_capacity'], '+'.join(record['groups']) or 'baseline',
                             record['independent']['status'], record['optimistic_envelope']['status']])


if __name__ == '__main__':
    main()
