"""Three-panel video for the adaptation experiment, rendered offscreen.

  1. normal model, published controller
  2. both gluteus groups at 20%, published controller
  3. both gluteus groups at 20%, adapted controller

  python scripts/adaptation_video.py --name glut_med_max_020
Writes results/adaptation/<name>/adaptation_comparison.mp4 and .png, plus
the recorded runs (video_runs.json) so the outcome shown is the outcome measured.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_weakness_sweep as sweep  # noqa: E402

PANEL_W, PANEL_H, BAR = 480, 560, 70


def record(groups, capacity, model_path, env_path):
    import gymnasium as gym
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from DynSyn import SAC_DynSyn
    from wrapper import MuscleNormWrapper
    config = sweep._worker['config']
    policy = SAC_DynSyn.load(str(model_path), device='cpu', custom_objects=sweep.INFERENCE_OBJECTS)
    options = dict(config['single_env_kwargs'])
    options.update(random_init=False, reset_noise_scale=0.0, gait_cycles=3, qpos_diff_th=1e9)
    env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
    base = env.unwrapped
    model, data = base.model, base.data
    norm = VecNormalize.load(str(env_path), DummyVecEnv([lambda: env]))
    norm.training = False
    norm.norm_reward = False
    ids = [model.actuator(m).id for g in groups for m in sweep.GROUPS[g]]
    model.actuator_gainprm[ids, 2] *= capacity
    obs = norm.reset()
    pelvis = model.body('pelvis').id
    h0 = float(data.xpos[pelvis, 2])
    rec = {'time': [], 'qpos': [], 'act': [], 'error': []}

    def keep():
        rec['time'].append(float(data.time))
        rec['qpos'].append(data.qpos.copy())
        rec['act'].append(data.act.copy())
        rec['error'].append(float(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean()))

    keep()
    fell_at, extra = None, None
    while True:
        obs, _, done, _ = norm.step(policy.predict(obs, deterministic=True)[0])
        if done[0]:
            break
        keep()
        if extra is not None:
            extra -= 1
            if extra == 0:
                break
        elif fell_at is None and data.xpos[pelvis, 2] < sweep.FALL_RATIO * h0:
            fell_at, extra = float(data.time), 40   # let the fall play out briefly
    norm.close()
    run = {k: np.asarray(v) for k, v in rec.items()}
    run['fell_at'] = fell_at
    return run


def font(size):
    from PIL import ImageFont
    import matplotlib
    path = Path(matplotlib.get_data_path()) / 'fonts/ttf/DejaVuSans-Bold.ttf'
    return ImageFont.truetype(str(path), size)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--step', default='final')
    args = parser.parse_args()
    import imageio.v2 as imageio
    import mujoco
    from PIL import Image, ImageDraw

    folder = ROOT / 'results/adaptation' / args.name
    config = json.loads((folder / 'config.json').read_text())
    groups, capacity = tuple(config['groups']), config['capacity']
    original = ROOT / 'vendor/checkpoints/LocomotionLegs/checkpoint'
    prefix = 'final_' if args.step == 'final' else ''
    suffix = '' if args.step == 'final' else f'_{args.step}'
    adapted_model = folder / f'{prefix}model{suffix}.zip'
    adapted_env = folder / f'{prefix}env{suffix}.zip'

    sweep.init_worker()
    panels = [
        ('Normal model', 'Tüm kaslar %100', (), 1.0, original / 'best_model.zip', original / 'best_env.zip'),
        ('Zayıf + alışmamış kontrolcü', 'Sağ gluteus med+max %20', groups, capacity,
         original / 'best_model.zip', original / 'best_env.zip'),
        ('Zayıf + alışmış kontrolcü', 'Sağ gluteus med+max %20', groups, capacity, adapted_model, adapted_env),
    ]
    runs = []
    for title, sub, g, c, m, e in panels:
        run = record(g, c, m, e)
        runs.append(run)
        print(title, '| süre', round(float(run['time'][-1]), 2), 's | düştü:', run['fell_at'], flush=True)

    import gymnasium as gym
    cfg = sweep._worker['config']
    models = []
    for _, _, g, _, _, _ in panels:
        model = gym.make(cfg['env_name'], render_mode=None, **cfg['single_env_kwargs']).unwrapped.model
        model.vis.global_.offwidth, model.vis.global_.offheight = PANEL_W, PANEL_H
        for group in g:
            for m in sweep.GROUPS[group]:
                tid = int(model.actuator_trnid[model.actuator(m).id, 0])
                model.tendon_rgba[tid] = (1, 0.45, 0.05, 1)
                model.tendon_width[tid] = 0.008
        models.append(model)
    datas = [mujoco.MjData(m) for m in models]
    renderers = [mujoco.Renderer(m, PANEL_H, PANEL_W) for m in models]
    opt = mujoco.MjvOption()
    opt.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = True
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth, cam.elevation, cam.distance = 90, -15, 3.4
    big, small = font(20), font(15)

    span = max(float(r['time'][-1]) for r in runs) + 0.5
    count = int(np.ceil(span * 60))          # half speed at 30 fps
    out_mp4 = folder / 'adaptation_comparison.mp4'
    with imageio.get_writer(out_mp4, fps=30, codec='libx264') as writer:
        for frame in range(count):
            at = frame / 60
            canvas = Image.new('RGB', (PANEL_W * len(panels), PANEL_H + BAR), (24, 24, 28))
            draw = ImageDraw.Draw(canvas)
            for i, (run, model, data, renderer, (title, sub, *_)) in enumerate(zip(runs, models, datas, renderers, panels)):
                k = max(0, int(np.searchsorted(run['time'], at, side='right')) - 1)
                data.qpos[:] = run['qpos'][k]
                data.act[:] = run['act'][k]
                mujoco.mj_forward(model, data)
                cam.lookat[:] = data.xpos[model.body('pelvis').id]
                cam.lookat[2] = 0.9
                renderer.update_scene(data, camera=cam, scene_option=opt)
                canvas.paste(Image.fromarray(renderer.render()), (i * PANEL_W, BAR))
                if run['fell_at'] is not None and at >= run['fell_at']:
                    status, color = f'DÜŞTÜ ({run["fell_at"]:.2f} s)', (255, 90, 80)
                elif at > run['time'][-1]:
                    status, color = 'Yürüdü, 3 adım döngüsü tamam', (110, 220, 120)
                else:
                    status, color = f'{min(at, float(run["time"][-1])):.2f} s', (230, 230, 230)
                x = i * PANEL_W + 14
                draw.text((x, 8), title, font=big, fill=(240, 240, 240))
                draw.text((x, 34), sub, font=small, fill=(255, 160, 80) if i else (180, 180, 180))
                draw.text((x, BAR + 10), status, font=big, fill=color)
            image = np.asarray(canvas)
            writer.append_data(image)
            if frame == int(min(span - 0.6, 3.45) * 60):
                imageio.imwrite(folder / 'adaptation_comparison.png', image)
    summary = [{'panel': p[0], 'fell_at_s': r['fell_at'], 'duration_s': float(r['time'][-1]),
                'max_mean_coordinate_error_rad': float(r['error'].max())} for p, r in zip(panels, runs)]
    (folder / 'video_runs.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Video:', out_mp4)


if __name__ == '__main__':
    main()
