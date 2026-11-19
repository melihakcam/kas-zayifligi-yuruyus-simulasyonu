"""Run matched forward rollouts with the published policy and active-only weakness."""
import json
from pathlib import Path
import sys

import gymnasium as gym
import mujoco
import numpy as np
import torch
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/msgym/DynSyn-SAC/SB3-Scripts'))
import msgym
from DynSyn import SAC_DynSyn
from wrapper import MuscleNormWrapper


def rollout(policy, config, capacity, output):
    options = dict(config['single_env_kwargs'])
    options.update(random_init=False, reset_noise_scale=0.0, gait_cycles=3)
    env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
    base = env.unwrapped
    model, data = base.model, base.data
    checkpoint = ROOT / 'vendor/checkpoints/LocomotionLegs/checkpoint'
    normalizer = VecNormalize.load(str(checkpoint / 'best_env.zip'), DummyVecEnv([lambda: env]))
    normalizer.training = False
    normalizer.norm_reward = False
    observation = normalizer.reset()
    initial_qpos = data.qpos.copy()
    initial_qvel = data.qvel.copy()
    aid = model.actuator('tibant_r').id
    if model.actuator_gainprm[aid, 2] <= 0:
        raise ValueError('Expected explicit active muscle force parameter')
    passive_before = model.actuator_biasprm.copy()
    # Gain and bias parameters are separate: reduce only the active component.
    data.act[aid] = 1
    mujoco.mj_forward(model, data)
    force_one = float(data.actuator_force[aid])
    data.act[aid] = 0
    mujoco.mj_forward(model, data)
    force_zero = float(data.actuator_force[aid])
    model.actuator_gainprm[aid, 2] *= capacity
    data.act[aid] = 1
    mujoco.mj_forward(model, data)
    weakened_one = float(data.actuator_force[aid])
    data.act[aid] = 0
    mujoco.mj_forward(model, data)
    weakened_zero = float(data.actuator_force[aid])
    if abs((weakened_one - weakened_zero) - capacity * (force_one - force_zero)) > 1e-8:
        raise ValueError('Active capacity intervention failed')
    if abs(weakened_zero - force_zero) > 1e-8 or not np.array_equal(passive_before, model.actuator_biasprm):
        raise ValueError('Passive muscle force changed')
    # Reset to the same state, with the intervention already present in observations.
    observation = normalizer.reset()
    if not np.array_equal(initial_qpos, data.qpos) or not np.array_equal(initial_qvel, data.qvel):
        raise ValueError('Initial states did not match after reset')
    records = {key: [] for key in ('time', 'qpos', 'qvel', 'activation', 'ctrl', 'toe_height', 'ankle_angle')}
    original = base.do_simulation
    ankle_index = int(model.jnt_qposadr[model.joint('ankle_angle_r').id])
    toe_id = model.body('toes_r').id
    final = {}

    def record(ctrl, frames):
        for _ in range(frames):
            data.ctrl[:] = ctrl
            mujoco.mj_forward(model, data)
            for key, value in (('time', data.time), ('qpos', data.qpos), ('qvel', data.qvel),
                               ('activation', data.act), ('ctrl', data.ctrl),
                               ('toe_height', data.xpos[toe_id, 2]), ('ankle_angle', data.qpos[ankle_index])):
                records[key].append(np.asarray(value).copy())
            original(ctrl, 1)
        final.update(time_s=float(data.time), healthy=bool(base.is_healthy),
                     mean_coordinate_error=float(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean()))

    base.do_simulation = record
    try:
        for step in range(int(np.ceil(3 * base.terminate_time / base.dt)) + 2):
            action, _ = policy.predict(observation, deterministic=True)
            observation, _, done, _ = normalizer.step(action)
            if done[0]:
                break
    finally:
        normalizer.close()
    arrays = {key: np.asarray(value) for key, value in records.items()}
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ValueError('Nonfinite forward rollout')
    np.savez_compressed(output, **arrays)
    return {'capacity': capacity, 'final': final, 'physics_samples': len(arrays['time']),
            'active_force_scale_verified': True, 'passive_force_unchanged_verified': True}, arrays


def main():
    torch.set_num_threads(1)
    torch.manual_seed(0)
    output = ROOT / 'results/visual_comparison'
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = ROOT / 'vendor/checkpoints/LocomotionLegs'
    config = json.loads((checkpoint / 'locomotionLegs.json').read_text())
    policy = SAC_DynSyn.load(str(checkpoint / 'checkpoint/best_model.zip'), device='cpu')
    report = {'scope': 'Matched initial conditions and published controller; active tibant_r weakness only; no retraining',
              'interpretation': 'Forward response illustrates this controller. It does not prove impossibility for other controllers.',
              'rollouts': []}
    arrays = []
    for capacity, name in ((1.0, 'normal'), (0.4, 'weak')):
        entry, states = rollout(policy, config, capacity, output / f'{name}.npz')
        arrays.append(states)
        report['rollouts'].append(entry)
        print(name, entry, flush=True)
    if not np.array_equal(arrays[0]['qpos'][0], arrays[1]['qpos'][0]):
        raise ValueError('Forward comparison initial conditions differ')
    n = min(len(a['time']) for a in arrays)
    report['matched_initial_conditions_verified'] = True
    report['max_right_ankle_difference_deg'] = float(np.rad2deg(np.abs(arrays[0]['ankle_angle'][:n] - arrays[1]['ankle_angle'][:n])).max())
    report['max_right_toe_body_height_difference_cm'] = float(100*np.abs(arrays[0]['toe_height'][:n] - arrays[1]['toe_height'][:n]).max())
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
