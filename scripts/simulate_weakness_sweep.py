"""Forward-simulation sweep: weaken muscle groups and let the published controller walk.

Every scenario starts from the same deterministic state as the baseline and
uses the same controller without retraining. Only the active force component
(gainprm[2]) of the chosen muscles is scaled; passive forces stay unchanged.

The environment's own termination (mean coordinate error above qpos_diff_th)
is switched off so every run lasts three gait cycles unless the model falls.
Outcomes are classified afterwards:
  - walked:   mean coordinate error stayed under the controller threshold
  - deviated: threshold crossed but the pelvis stayed up
  - fell:     pelvis height dropped below FALL_RATIO of its initial value
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
import json
import os
from pathlib import Path
import sys
import time as clock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'right_tibialis_anterior': ['tibant_r'],
    'right_soleus': ['soleus_r'],
    'right_gastrocnemius': ['gasmed_r', 'gaslat_r'],
    'right_vasti': ['vasint_r', 'vaslat_r', 'vasmed_r'],
    'right_hamstrings': ['bflh_r', 'semimem_r', 'semiten_r'],
    'right_gluteus_medius': ['glmed1_r', 'glmed2_r', 'glmed3_r'],
    'right_gluteus_maximus': ['glmax1_r', 'glmax2_r', 'glmax3_r'],
    'right_hip_flexors': ['iliacus_r', 'Ps_L1_VB_r', 'Ps_L1_TP_r', 'Ps_L1_L2_IVD_r', 'Ps_L2_TP_r',
                          'Ps_L2_L3_IVD_r', 'Ps_L3_TP_r', 'Ps_L3_L4_IVD_r', 'Ps_L4_TP_r',
                          'Ps_L4_L5_IVD_r', 'Ps_L5_TP_r', 'Ps_L5_VB_r'],
}
THRESHOLD = 0.06   # controller's training threshold, rad (mean |qpos - ref|)
FALL_RATIO = 0.7
_worker = {}


def init_worker(model_path=None, env_path=None):
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    import torch
    torch.set_num_threads(1)
    sys.path.insert(0, str(ROOT / 'vendor/msgym/DynSyn-SAC/SB3-Scripts'))
    import msgym  # noqa: F401  registers the environments
    from DynSyn import SAC_DynSyn
    checkpoint = ROOT / 'vendor/checkpoints/LocomotionLegs'
    _worker['config'] = json.loads((checkpoint / 'locomotionLegs.json').read_text())
    # Inference only: skip the ~2.8 GiB training replay buffer.
    _worker['policy'] = SAC_DynSyn.load(str(model_path or checkpoint / 'checkpoint/best_model.zip'), device='cpu',
                                        custom_objects={'buffer_size': 1})
    _worker['env_path'] = str(env_path or checkpoint / 'checkpoint/best_env.zip')


def rollout(job):
    import gymnasium as gym
    import mujoco
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from wrapper import MuscleNormWrapper

    groups, capacity, seed, noise = job
    config, policy = _worker['config'], _worker['policy']
    options = dict(config['single_env_kwargs'])
    options.update(random_init=False, reset_noise_scale=noise, gait_cycles=3, qpos_diff_th=1e9)
    env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
    base = env.unwrapped
    model, data = base.model, base.data
    normalizer = VecNormalize.load(_worker['env_path'], DummyVecEnv([lambda: env]))
    normalizer.training = False
    normalizer.norm_reward = False
    muscles = [m for g in groups for m in GROUPS[g]]
    ids = [model.actuator(m).id for m in muscles]
    passive = model.actuator_biasprm.copy()
    if np.any(model.actuator_gainprm[ids, 2] <= 0):
        raise ValueError('Expected explicit active force parameter')
    model.actuator_gainprm[ids, 2] *= capacity
    if not np.array_equal(passive, model.actuator_biasprm):
        raise ValueError('Passive parameters changed')
    if noise > 0:
        normalizer.seed(seed)
    observation = normalizer.reset()
    pelvis = model.body('pelvis').id
    start_height = float(data.xpos[pelvis, 2])
    times, errors, heights = [], [], []
    end_time = 3 * base.terminate_time
    try:
        while True:
            action, _ = policy.predict(observation, deterministic=True)
            observation, _, done, _ = normalizer.step(action)
            if done[0]:
                break
            times.append(float(data.time))
            errors.append(float(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean()))
            heights.append(float(data.xpos[pelvis, 2]))
            if heights[-1] < FALL_RATIO * start_height:
                break
    finally:
        normalizer.close()
    times, errors, heights = map(np.asarray, (times, errors, heights))
    over = np.flatnonzero(errors > THRESHOLD)
    fell = heights.size and heights.min() < FALL_RATIO * start_height
    outcome = 'fell' if fell else ('deviated' if over.size else 'walked')
    return {
        'groups': list(groups), 'remaining_active_capacity': capacity, 'outcome': outcome,
        'seed': seed, 'reset_noise_scale': noise,
        'simulated_time_s': float(times[-1]) if times.size else 0.0,
        'requested_time_s': float(end_time),
        'first_threshold_crossing_s': float(times[over[0]]) if over.size else None,
        'max_mean_coordinate_error_rad': float(errors.max()),
        'mean_coordinate_error_rad': float(errors.mean()),
        'min_pelvis_height_ratio': float(heights.min() / start_height),
        'error_trace': errors[::5].round(5).tolist(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--levels', type=float, nargs='+', default=[0.6, 0.4, 0.2, 0.0])
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument('--singles-only', action='store_true')
    parser.add_argument('--output', default='results/forward_sweep')
    parser.add_argument('--scenario', nargs='+', help='Groups joined by +; replaces the default grid')
    parser.add_argument('--seeds', type=int, default=1, help='Repeats with reset noise (seed 0..n-1)')
    parser.add_argument('--noise', type=float, default=0.0, help='Reset noise scale (training used 0.001)')
    args = parser.parse_args()
    scenarios = [(g,) for g in GROUPS]
    if not args.singles_only:
        scenarios += list(combinations(GROUPS, 2))
    if args.scenario:
        scenarios = [tuple(v.split('+')) for v in args.scenario]
        if any(g not in GROUPS for s in scenarios for g in s):
            raise ValueError('Unknown group')
    seeds = range(args.seeds)
    jobs = [((), 1.0, k, args.noise) for k in seeds] +            [(s, c, k, args.noise) for c in args.levels for s in scenarios for k in seeds]
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    results, started = [], clock.time()
    with ProcessPoolExecutor(args.workers, initializer=init_worker) as pool:
        for i, result in enumerate(pool.map(rollout, jobs), 1):
            results.append(result)
            print(f"[{i}/{len(jobs)} {clock.time() - started:.0f}s] {result['remaining_active_capacity']:.2f} s{result['seed']} "
                  f"{'+'.join(result['groups']) or 'baseline'}: {result['outcome']} "
                  f"(max err {result['max_mean_coordinate_error_rad']:.3f}, t={result['simulated_time_s']:.2f})",
                  flush=True)
            report = {'scope': 'Published LocomotionLegs controller, deterministic start, active force only, no retraining',
                      'groups': GROUPS, 'threshold_rad': THRESHOLD, 'fall_ratio': FALL_RATIO,
                      'interpretation': ('Outcomes describe this controller without adaptation. A failure does not '
                                         'prove that a person or another controller could not walk.'),
                      'results': results}
            (output / 'sweep.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
