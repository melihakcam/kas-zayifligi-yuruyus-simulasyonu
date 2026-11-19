"""Fine-tune the published controller on a weakened model (adaptation experiment).

Question: if the controller is allowed to adapt to the weakness, can it keep
walking? Starting point is the published LocomotionLegs checkpoint; the
environment, reward and termination are the original training settings, so
the controller is still rewarded for tracking the normal reference gait.
Only the active force of the chosen muscle groups is scaled.

  python scripts/adapt_controller.py --groups right_gluteus_medius right_gluteus_maximus \
      --capacity 0.2 --steps 200000 --envs 4 --name glut_020
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SB3 = ROOT / 'vendor/msgym/DynSyn-SAC/SB3-Scripts'
sys.path.insert(0, str(SB3))
sys.path.insert(0, str(Path(__file__).resolve().parent))
CHECKPOINT = ROOT / 'vendor/checkpoints/LocomotionLegs'


def make_env(config, groups, capacity, seed):
    def factory():
        import gymnasium as gym
        import msgym  # noqa: F401
        from stable_baselines3.common.monitor import Monitor
        from wrapper import MuscleNormWrapper
        import simulate_weakness_sweep as sweep
        env = gym.make(config['env_name'], render_mode=None, **config['single_env_kwargs'])
        model = env.unwrapped.model
        ids = [model.actuator(m).id for g in groups for m in sweep.GROUPS[g]]
        model.actuator_gainprm[ids, 2] *= capacity
        env = Monitor(MuscleNormWrapper(env))
        env.reset(seed=seed)
        return env
    return factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--groups', nargs='+', required=True)
    parser.add_argument('--capacity', type=float, required=True)
    parser.add_argument('--steps', type=int, default=200_000)
    parser.add_argument('--envs', type=int, default=4)
    parser.add_argument('--buffer', type=int, default=50_000)
    parser.add_argument('--learning-starts', type=int, default=4_000)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--save-every', type=int, default=25_000)
    parser.add_argument('--name', required=True)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--resume', action='store_true',
                        help='continue from the latest model_<n>.zip in the output folder')
    args = parser.parse_args()

    import torch
    torch.set_num_threads(2)
    import msgym  # noqa: F401
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
    from DynSyn import SAC_DynSyn
    import simulate_weakness_sweep as sweep

    if any(g not in sweep.GROUPS for g in args.groups):
        raise ValueError('Unknown group')
    config = json.loads((CHECKPOINT / 'locomotionLegs.json').read_text())
    out = ROOT / 'results/adaptation' / args.name
    out.mkdir(parents=True, exist_ok=True)
    (out / 'config.json').write_text(json.dumps(vars(args), indent=2), encoding='utf-8')

    # Start from the published checkpoint, or from the latest saved one with --resume.
    # The replay buffer is not saved, so a resumed run refills it first.
    offset = 0
    model_file = CHECKPOINT / 'checkpoint/best_model.zip'
    env_file = CHECKPOINT / 'checkpoint/best_env.zip'
    saved = sorted(int(p.stem.split('_')[1]) for p in out.glob('model_*.zip'))
    if args.resume and saved:
        offset = saved[-1]
        model_file, env_file = out / f'model_{offset}.zip', out / f'env_{offset}.zip'
        print(f'Resuming from step {offset}', flush=True)
    if offset >= args.steps or (args.resume and (out / 'final_model.zip').exists()):
        print('Already finished', flush=True)
        return

    vec = SubprocVecEnv([make_env(config, args.groups, args.capacity, args.seed + offset + i)
                         for i in range(args.envs)])
    vec = VecNormalize.load(str(env_file), vec)
    vec.training = True          # observation statistics may follow the new gait
    vec.norm_reward = False
    model = SAC_DynSyn.load(str(model_file), env=vec, device='cpu',
                            custom_objects={'buffer_size': args.buffer, 'learning_starts': args.learning_starts,
                                            'learning_rate': args.lr, 'lr_schedule': lambda _: args.lr,
                                            'tensorboard_log': None})
    model.learning_rate = args.lr
    model._setup_lr_schedule()

    class Log(BaseCallback):
        def __init__(self):
            super().__init__()
            self.start = time.time()
            progress = out / 'progress.json'
            self.rows = [r for r in json.loads(progress.read_text()) if r['steps'] <= offset] \
                if offset and progress.exists() else []
            self.next_save = offset + args.save_every

        def _on_step(self):
            n = offset + self.num_timesteps
            if n >= self.next_save:
                self.next_save += args.save_every
                self.model.save(out / f'model_{n}.zip')
                vec.save(str(out / f'env_{n}.zip'))
            if self.n_calls % 250 == 0:
                eps = list(self.model.ep_info_buffer)[-20:]
                row = {'steps': int(n), 'seconds': round(time.time() - self.start, 1),
                       'steps_per_s': round(self.num_timesteps / max(1e-9, time.time() - self.start), 1),
                       'remaining_min': round((args.steps - n) / max(1e-9, self.num_timesteps)
                                              * (time.time() - self.start) / 60),
                       'episode_length_mean': float(np.mean([e['l'] for e in eps])) if eps else None,
                       'episode_reward_mean': float(np.mean([e['r'] for e in eps])) if eps else None}
                self.rows.append(row)
                (out / 'progress.json').write_text(json.dumps(self.rows, indent=1), encoding='utf-8')
                print(json.dumps(row), flush=True)
            return True

    model.num_timesteps = 0
    model.learn(total_timesteps=args.steps - offset, callback=Log(), reset_num_timesteps=True, log_interval=10_000)
    model.save(out / 'final_model.zip')
    vec.save(str(out / 'final_env.zip'))
    vec.close()


if __name__ == '__main__':
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    main()
