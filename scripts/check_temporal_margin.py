"""Measure torque error in a relaxation containing only right ankle/foot DOFs.

Removing other torque equations relaxes the full problem. A positive optimum
therefore bounds the full problem's required error from below, numerically.
"""
import json
from pathlib import Path

import mujoco
import numpy as np
from scipy import sparse
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]


def margin(active, target, tau, dt, stride, rate_scale, save=None, details=None):
    steps, dofs, muscles = active.shape
    balance = sparse.block_diag([sparse.csr_matrix(a) for a in active], format='csr')
    slack = -np.ones((steps * dofs, 1))
    inequalities = [sparse.hstack((balance, slack)), sparse.hstack((-balance, slack))]
    rhs = [target.ravel(), -target.ravel()]
    if rate_scale is not None:
        up = np.maximum(0, 1 - 2 * dt / (tau[:, 0] * rate_scale)) ** stride
        down = np.maximum(0, 1 - 2 * dt / (tau[:, 1] * rate_scale)) ** stride
        if np.any(2 * dt > tau * rate_scale):
            raise ValueError('Rate scaling invalidates nonnegative repeated envelope')
        first = sparse.diags(np.ones(steps - 1), 0, shape=(steps - 1, steps))
        next_ = sparse.diags(np.ones(steps - 1), 1, shape=(steps - 1, steps))
        rising = sparse.kron(next_, sparse.eye(muscles)) - sparse.kron(first, sparse.diags(up))
        falling = sparse.kron(first, sparse.diags(down)) - sparse.kron(next_, sparse.eye(muscles))
        rate = sparse.vstack((rising, falling), format='csr')
        inequalities.append(sparse.hstack((rate, np.zeros((rate.shape[0], 1)))))
        rhs += [np.tile(1 - up, steps - 1), np.zeros((steps - 1) * muscles)]
    inequality = sparse.vstack(inequalities, format='csr')
    limits = np.concatenate(rhs)
    objective = np.zeros(steps * muscles + 1)
    objective[-1] = 1
    result = linprog(objective, A_ub=inequality, b_ub=limits,
                     bounds=[(0, 1)] * (steps * muscles) + [(0, None)], method='highs',
                     options={'time_limit': 30, 'dual_feasibility_tolerance': 1e-8,
                              'primal_feasibility_tolerance': 1e-8})
    if not result.success:
        return {'status': 'unresolved', 'solver_status': int(result.status)}
    violation = float(max(0, np.max(inequality @ result.x - limits)))
    # HiGHS dual marginals and variable-bound marginals provide a second check
    # on the numerical optimum; this is not an interval-arithmetic proof.
    lower_bound = float(limits @ result.ineqlin.marginals + np.sum(result.upper.marginals[:-1]))
    stationarity = objective - inequality.T @ result.ineqlin.marginals - result.lower.marginals - result.upper.marginals
    dual_error = float(np.max(np.abs(stationarity)))
    dual_sign_error = float(max(0, result.ineqlin.marginals.max(), result.upper.marginals.max(),
                                -result.lower.marginals.min()))
    if violation > 1e-7 or dual_error > 1e-7 or dual_sign_error > 1e-7 or abs(result.fun - lower_bound) > 1e-7:
        return {'status': 'verification_failed', 'max_constraint_violation': violation,
                'dual_stationarity_error': dual_error, 'dual_sign_error': dual_sign_error}
    if details is not None:
        details.update(solution=result.x[:-1].reshape(steps, muscles),
                       delivered=(balance @ result.x[:-1]).reshape(steps, dofs),
                       duals=result.ineqlin.marginals.copy(), steps=steps, dofs=dofs, muscles=muscles)
    if save is not None:
        np.savez_compressed(save, activation=result.x[:-1].reshape(steps, muscles), target_torque=target,
                            delivered_torque=(balance @ result.x[:-1]).reshape(steps, dofs))
    return {'status': 'optimal', 'minimum_max_torque_error_Nm': float(result.fun),
            'numerical_dual_lower_bound_Nm': lower_bound,
            'dual_stationarity_error': dual_error, 'dual_sign_error': dual_sign_error,
            'primal_dual_gap': float(result.fun - lower_bound), 'max_constraint_violation': violation}


def main():
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'))
    joints = ['ankle_angle_r', 'subtalar_angle_r', 'mtp_angle_r']
    rows = [int(model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)]) for name in joints]
    if any(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) < 0 for name in joints):
        raise ValueError('Missing target joint')
    summary = json.loads((ROOT / 'results/baseline/summary.json').read_text())
    if not summary['completed_requested_cycles'] or summary['integrator_id'] != 0:
        raise ValueError('Completed Euler baseline required')
    with np.load(ROOT / 'results/baseline/trajectory.npz', allow_pickle=False) as source:
        selected = np.flatnonzero((source['time'] >= 1.17 - 1e-9) & (source['time'] <= 2.34 + 1e-9))
        active = source['linear_active'][selected][:, rows, :]
        target = (source['torque'][selected] - source['linear_offset'][selected])[:, rows]
        keep = np.any(np.abs(active) > 1e-12, axis=(0, 1))
        active = active[:, :, keep]
        names = source['actuator_names'][keep].tolist()
        tau = source['activation_time_constants'][keep]
        witness = source['activation'][selected][:, keep]
    dt = summary['physics_timestep_s']
    if len(selected) < 2 or np.any(np.diff(selected) != 1):
        raise ValueError('Consecutive samples required')
    output = ROOT / 'results/temporal_margin'
    output.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'Right ankle/foot relaxation of the fixed recorded trajectory; free initial activation',
              'joints': joints, 'muscles': names, 'sample_count': len(selected),
              'physics_timestep_s': dt, 'scenarios': [],
              'interpretation': 'Positive verified LP optimum is a numerical lower bound on required torque error, conditional on the model and recorded states.'}
    witness_error = float(np.max(np.abs(np.einsum('tjm,tm->tj', active, witness) - target)))
    if witness_error > 1e-7:
        raise ValueError('Reduced torque reconstruction failed')
    report['baseline_witness_torque_error'] = witness_error
    for remaining in (1.0, 0.8, 0.6, 0.5, 0.4):
        scale = np.ones(len(names))
        scale[names.index('tibant_r')] = remaining
        for rate_scale in (None, 1.0, 0.5):
            tag = 'independent' if rate_scale is None else f'rate_{rate_scale}'
            result = margin(active * scale, target, tau, dt, 1, rate_scale,
                            output / f'{remaining:.2f}_{tag}.npz')
            result.update(remaining_active_capacity=remaining, activation_time_constant_scale=rate_scale)
            report['scenarios'].append(result)
            (output / 'margin.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(remaining, rate_scale, result, flush=True)


if __name__ == '__main__':
    main()
