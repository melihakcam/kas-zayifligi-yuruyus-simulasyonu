"""Check the research condition on an explicitly artificial three-actuator system."""

import json
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]


def solve(failed, dynamic):
    # This is a two-instant force allocation example, not a physiological muscle model.
    capacities = np.array([0.45, 0.45, 1.0])
    capacities[list(failed)] = 0.0
    target = np.array([0.45, 0.80])
    rate_limits = np.array([0.45, 0.45, 0.10])
    equality = np.array([[1, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 1]])
    change = np.hstack((-np.eye(3), np.eye(3)))
    result = linprog(
        np.zeros(6), A_eq=equality, b_eq=target,
        A_ub=np.vstack((change, -change)) if dynamic else None,
        b_ub=np.tile(rate_limits, 2) if dynamic else None,
        bounds=[(0.0, cap) for cap in np.tile(capacities, 2)], method='highs',
    )
    if result.status not in (0, 2):
        raise RuntimeError(f'Solver outcome cannot establish feasibility: {result.message}')
    solution = result.x.reshape(2, 3) if result.success else None
    if solution is not None:
        if np.max(np.abs(solution.sum(axis=1) - target)) > 1e-8:
            raise RuntimeError('Force balance residual exceeded tolerance')
        if dynamic and np.any(np.abs(np.diff(solution, axis=0)[0]) > rate_limits + 1e-8):
            raise RuntimeError('Rate constraint residual exceeded tolerance')
    return {'feasible': bool(result.success), 'solver_status': result.status,
            'forces': solution.tolist() if solution is not None else None}


def main():
    names = ('A', 'B', 'C')
    scenarios = {}
    for size in range(3):
        for failed in combinations(range(3), size):
            label = '+'.join(names[i] for i in failed) or 'baseline'
            scenarios[label] = {'independent': solve(failed, False), 'time_linked': solve(failed, True)}
    for label in ('baseline', 'A', 'B'):
        if not scenarios[label]['time_linked']['feasible']:
            raise RuntimeError(f'Expected a feasible control scenario: {label}')
    if not scenarios['A+B']['independent']['feasible'] or scenarios['A+B']['time_linked']['feasible']:
        raise RuntimeError('Expected a static-feasible, dynamic-infeasible pair')
    # Independent check. With A+B absent, C must increase by .35; its bound is .10.
    report = {
        'kind': 'synthetic numerical check', 'physiological_evidence': False,
        'scope': 'two fixed time instants, arbitrary force units, complete actuator removal',
        'independent_infeasibility_check': {'required_change_C': 0.35, 'allowed_change_C': 0.10},
        'scenarios': scenarios,
    }
    output = ROOT / 'results' / 'synthetic'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'pilot.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for name, scenario in scenarios.items():
        print(f'{name:8} independent={scenario["independent"]["feasible"]} '
              f'time_linked={scenario["time_linked"]["feasible"]}')
    print('Synthetic checks passed. Physiological evidence requires the real-model experiment.')


if __name__ == '__main__':
    main()
