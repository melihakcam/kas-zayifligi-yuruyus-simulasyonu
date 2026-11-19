"""Run the published CPU policy and record every physics step for fixed-motion analysis."""

import argparse
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
import msgym  # registers the pinned environments
from DynSyn import SAC_DynSyn
from wrapper import MuscleNormWrapper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--video', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(0)
    output = ROOT / 'results/baseline'
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = ROOT / 'vendor/checkpoints/LocomotionLegs'
    config = json.loads((checkpoint / 'locomotionLegs.json').read_text())
    options = dict(config['single_env_kwargs'])
    options.update(random_init=False, reset_noise_scale=0.0, gait_cycles=args.cycles)
    env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
    base = env.unwrapped
    model, data = base.model, base.data
    if model.na != model.nu or not np.array_equal(model.actuator_actadr, np.arange(model.nu)):
        raise ValueError('This recorder requires one activation state per muscle actuator')
    normalizer = VecNormalize.load(str(checkpoint / 'checkpoint/best_env.zip'), DummyVecEnv([lambda: env]))
    normalizer.training = False
    normalizer.norm_reward = False
    policy = SAC_DynSyn.load(str(checkpoint / 'checkpoint/best_model.zip'), device='cpu')
    observation = normalizer.reset()
    print('Policy and environment loaded', flush=True)
    renderer = None
    writer = None
    if args.video:
        import imageio.v2 as imageio
        model.vis.quality.shadowsize = 1024
        model.vis.global_.offwidth = 640
        model.vis.global_.offheight = 480
        renderer = mujoco.Renderer(model, height=480, width=640)
        writer = imageio.get_writer(output / 'normal_walk.mp4', fps=50, codec='libx264')
    records = {key: [] for key in ('time', 'qpos', 'qvel', 'qacc', 'activation', 'ctrl',
                                  'torque', 'passive_torque', 'bias_torque', 'constraint_torque',
                                  'linear_active', 'linear_offset', 'dynamics_residual')}
    original_simulate = base.do_simulation
    last_control_state = {}

    def record_step(ctrl, frames):
        for _ in range(frames):
            data.ctrl[:] = ctrl
            mujoco.mj_forward(model, data)
            activation = data.act.copy()
            torque = data.qfrc_actuator.copy()
            moment = np.zeros((model.nu, model.nv))
            if data.actuator_moment.ndim == 2:
                moment[:] = data.actuator_moment
            else:
                mujoco.mju_sparse2dense(moment, data.actuator_moment,
                                       data.moment_rownnz, data.moment_rowadr, data.moment_colind)
            data.act[:] = 0.0
            mujoco.mj_fwdActuation(model, data)
            offset = data.qfrc_actuator.copy()
            force_zero = data.actuator_force.copy()
            data.act[:] = 1.0
            mujoco.mj_fwdActuation(model, data)
            active = moment.T * (data.actuator_force - force_zero)[None, :]
            data.act[:] = activation
            mujoco.mj_fwdActuation(model, data)
            if np.max(np.abs(active @ activation + offset - torque)) > 1e-7:
                raise ValueError('Activation-to-torque linearization failed at fixed state')
            mass = np.zeros((model.nv, model.nv))
            mujoco.mj_fullM(model, data, mass)
            residual = (mass @ data.qacc + data.qfrc_bias - data.qfrc_passive
                        - data.qfrc_actuator - data.qfrc_constraint - data.qfrc_applied)
            records['time'].append(float(data.time))
            for key, value in (
                ('qpos', data.qpos), ('qvel', data.qvel), ('qacc', data.qacc),
                ('activation', activation), ('ctrl', data.ctrl), ('torque', torque),
                ('passive_torque', data.qfrc_passive), ('bias_torque', data.qfrc_bias),
                ('constraint_torque', data.qfrc_constraint), ('linear_active', active),
                ('linear_offset', offset), ('dynamics_residual', residual),
            ):
                records[key].append(np.asarray(value).copy())
            if writer is not None and len(records['time']) % 10 == 0:
                renderer.update_scene(data, camera='record_camera')
                writer.append_data(renderer.render())
            original_simulate(ctrl, 1)
        last_control_state.update(time_s=float(data.time), healthy=bool(base.is_healthy),
                                  mean_coordinate_error=float(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean()))

    base.do_simulation = record_step
    control_steps = 0
    completed = False
    end_time = args.cycles * base.terminate_time
    try:
        while control_steps < int(np.ceil(end_time / base.dt)) + 2:
            action, _ = policy.predict(observation, deterministic=True)
            observation, reward, done, info = normalizer.step(action)
            control_steps += 1
            if control_steps % 50 == 0:
                print(f'Recorded {len(records["time"])} physics samples', flush=True)
            if done[0]:
                # The source environment sets BOTH terminated and truncated at its horizon.
                # SB3's TimeLimit flag therefore stays false even on a successful completion.
                completed = bool(last_control_state['time_s'] >= end_time - 1e-8
                                 and last_control_state['healthy'])
                break
    finally:
        if writer is not None:
            writer.close()
        if renderer is not None:
            renderer.close()
        normalizer.close()
    arrays = {key: np.asarray(value) for key, value in records.items()}
    if any(not np.isfinite(array).all() for array in arrays.values()):
        raise ValueError('Nonfinite baseline samples')
    arrays['joint_names'] = np.asarray([model.joint(i).name for i in range(model.njnt)])
    arrays['actuator_names'] = np.asarray([model.actuator(i).name for i in range(model.nu)])
    arrays['activation_time_constants'] = model.actuator_dynprm[:, :2].copy()
    np.savez_compressed(output / 'trajectory.npz', **arrays)
    summary = {
        'completed_requested_cycles': completed, 'requested_cycles': args.cycles,
        'control_steps': control_steps, 'physics_samples': len(arrays['time']),
        'last_recorded_time_s': float(arrays['time'][-1]),
        'physics_timestep_s': float(model.opt.timestep),
        'integrator_id': int(model.opt.integrator),
        'activation_dynamics': [mujoco.mjtDyn(int(value)).name for value in np.unique(model.actuator_dyntype)],
        'last_control_state': last_control_state,
        'max_dynamics_residual_Nm_or_N': float(np.max(np.abs(arrays['dynamics_residual']))),
        'max_abs_actuator_torque_Nm_or_N': float(np.max(np.abs(arrays['torque']))),
        'numpy_version': np.__version__, 'mujoco_version': mujoco.__version__,
        'torch_version': torch.__version__, 'reference_external_load_source': 'recorded simulator constraints',
        'scope': 'published policy, deterministic reference start, no reset noise',
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    if not completed:
        raise RuntimeError('Baseline did not finish the requested horizon. Do not interpret weakness experiments.')


if __name__ == '__main__':
    main()
