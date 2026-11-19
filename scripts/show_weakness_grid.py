"""Four-panel animation: normal, two single weaknesses, and their combination.

  --record   run the four forward simulations with the published controller
  (none)     open the interactive window
  --export   write an MP4 and a preview PNG
"""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_weakness_sweep as sweep  # noqa: E402

FOLDER = ROOT / 'results/visual_gluteus'
CAPACITY = 0.2
PANELS = [
    ('normal', (), 'NORMAL | Tum kaslar %100'),
    ('gluteus_medius', ('right_gluteus_medius',), 'Sadece gluteus medius %20'),
    ('gluteus_maximus', ('right_gluteus_maximus',), 'Sadece gluteus maximus %20'),
    ('both', ('right_gluteus_medius', 'right_gluteus_maximus'), 'IKISI BIRLIKTE %20'),
]


def record():
    import gymnasium as gym
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    sweep.init_worker()
    from wrapper import MuscleNormWrapper
    config, policy = sweep._worker['config'], sweep._worker['policy']
    FOLDER.mkdir(parents=True, exist_ok=True)
    summary = {'capacity': CAPACITY, 'scope': 'Published controller, deterministic start, active force only, no retraining',
               'panels': []}
    for name, groups, _ in PANELS:
        options = dict(config['single_env_kwargs'])
        options.update(random_init=False, reset_noise_scale=0.0, gait_cycles=3, qpos_diff_th=1e9)
        env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
        base = env.unwrapped
        model, data = base.model, base.data
        norm = VecNormalize.load(str(ROOT / 'vendor/checkpoints/LocomotionLegs/checkpoint/best_env.zip'),
                                 DummyVecEnv([lambda: env]))
        norm.training = False
        norm.norm_reward = False
        ids = [model.actuator(m).id for g in groups for m in sweep.GROUPS[g]]
        model.actuator_gainprm[ids, 2] *= CAPACITY
        obs = norm.reset()
        pelvis = model.body('pelvis').id
        h0 = float(data.xpos[pelvis, 2])
        rec = {k: [] for k in ('time', 'qpos', 'act', 'error')}

        def keep():
            rec['time'].append(float(data.time))
            rec['qpos'].append(data.qpos.copy())
            rec['act'].append(data.act.copy())
            rec['error'].append(float(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean()))

        keep()
        fell_at = None
        while True:
            action, _ = policy.predict(obs, deterministic=True)
            obs, _, done, _ = norm.step(action)
            if done[0]:
                break
            keep()
            if data.xpos[pelvis, 2] < sweep.FALL_RATIO * h0:
                fell_at = float(data.time)
                # Let the fall play out a little for the animation.
                for _ in range(40):
                    obs, _, done, _ = norm.step(policy.predict(obs, deterministic=True)[0])
                    if done[0]:
                        break
                    keep()
                break
        norm.close()
        arrays = {k: np.asarray(v) for k, v in rec.items()}
        np.savez_compressed(FOLDER / f'{name}.npz', **arrays)
        entry = {'name': name, 'groups': list(groups), 'fell_at_s': fell_at,
                 'max_mean_coordinate_error_rad': float(arrays['error'].max()),
                 'duration_s': float(arrays['time'][-1])}
        summary['panels'].append(entry)
        print(entry, flush=True)
    (FOLDER / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


class Viewer:
    def __init__(self, hidden=False):
        import glfw
        import mujoco
        self.glfw, self.mj = glfw, mujoco
        self.runs = [dict(np.load(FOLDER / f'{n}.npz')) for n, _, _ in PANELS]
        self.summary = json.loads((FOLDER / 'summary.json').read_text())
        path = str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml')
        self.models = [mujoco.MjModel.from_xml_path(path) for _ in PANELS]
        self.datas = [mujoco.MjData(m) for m in self.models]
        self.scenes = [mujoco.MjvScene(m, maxgeom=20000) for m in self.models]
        self.camera = mujoco.MjvCamera()
        self.opt = mujoco.MjvOption()
        self.opt.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = True
        for (_, groups, _), model in zip(PANELS, self.models):
            for g in groups:
                for m in sweep.GROUPS[g]:
                    tid = int(model.actuator_trnid[model.actuator(m).id, 0])
                    model.tendon_rgba[tid] = (1, 0.45, 0.05, 1)
                    model.tendon_width[tid] = 0.008
        if not glfw.init():
            raise RuntimeError('GLFW could not initialize')
        glfw.window_hint(glfw.VISIBLE, not hidden)
        self.window = glfw.create_window(1280, 720, 'Kalca kaslari: tek tek ve birlikte zayiflik', None, None)
        glfw.make_context_current(self.window)
        glfw.swap_interval(0 if hidden else 1)
        self.ctx = mujoco.MjrContext(self.models[0], mujoco.mjtFontScale.mjFONTSCALE_150)
        self.phase, self.speed, self.paused = 0.0, 0.5, False
        glfw.set_key_callback(self.window, self.key)

    def key(self, window, key, scan, action, mods):
        g = self.glfw
        if action != g.PRESS:
            return
        if key == g.KEY_ESCAPE:
            g.set_window_should_close(window, True)
        elif key == g.KEY_SPACE:
            self.paused = not self.paused
        elif key == g.KEY_R:
            self.phase = 0
        elif key in (g.KEY_1, g.KEY_2, g.KEY_3):
            self.speed = {g.KEY_1: 0.25, g.KEY_2: 0.5, g.KEY_3: 1.0}[key]

    def span(self):
        return max(float(r['time'][-1]) for r in self.runs) + 0.5

    def render(self):
        mj = self.mj
        width, height = self.glfw.get_framebuffer_size(self.window)
        bar = 48
        at = self.phase % self.span()
        w2, h2 = width // 2, (height - bar) // 2
        for i, ((name, groups, title), model, data, run) in enumerate(zip(PANELS, self.models, self.datas, self.runs)):
            k = max(0, int(np.searchsorted(run['time'], at, side='right')) - 1)
            data.qpos[:] = run['qpos'][k]
            data.act[:] = run['act'][k]
            mj.mj_forward(model, data)
            cam = self.camera
            cam.type = mj.mjtCamera.mjCAMERA_FREE
            cam.azimuth, cam.elevation, cam.distance = 90, -15, 3.4
            cam.lookat[:] = data.xpos[model.body('pelvis').id]
            cam.lookat[2] = 0.9
            mj.mjv_updateScene(model, data, self.opt, None, cam, mj.mjtCatBit.mjCAT_ALL, self.scenes[i])
            vp = mj.MjrRect((i % 2) * w2, bar + (1 - i // 2) * h2, w2, h2)
            mj.mjr_render(vp, self.scenes[i], self.ctx)
            info = self.summary['panels'][i]
            if info['fell_at_s'] is not None and at >= info['fell_at_s']:
                status = f'DUSTU ({info["fell_at_s"]:.2f} s)'
            elif at > run['time'][-1]:
                status = 'Yurudu, 3 dongu tamam'
            else:
                status = f'Sure {min(at, run["time"][-1]):.2f} s | eklem sapmasi {run["error"][k]:.3f} rad'
            mj.mjr_overlay(mj.mjtFontScale.mjFONTSCALE_100, mj.mjtGridPos.mjGRID_TOPLEFT, vp, title, status, self.ctx)
        mj.mjr_label(mj.MjrRect(0, 0, width, bar), mj.mjtFont.mjFONT_NORMAL,
                     f'Turuncu: zayiflatilan kaslar | SPACE: durdur | 1/2/3: hiz | R: bastan | ESC: kapat | Hiz: {self.speed:g}x',
                     0.12, 0.12, 0.12, 1, 0.92, 0.92, 0.92, self.ctx)
        return width, height

    def close(self):
        self.ctx.free()
        self.glfw.destroy_window(self.window)
        self.glfw.terminate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true')
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    if args.record:
        record()
        return
    app = Viewer(hidden=args.export)
    try:
        if args.export:
            import imageio.v2 as imageio
            duration = app.span()
            count = int(np.ceil(duration * 60))  # half speed at 30 fps
            with imageio.get_writer(FOLDER / 'gluteus_comparison.mp4', fps=30, codec='libx264') as writer:
                for frame in range(count):
                    app.phase = frame / 60
                    w, h = app.render()
                    px = np.empty((h, w, 3), dtype=np.uint8)
                    app.mj.mjr_readPixels(px, None, app.mj.MjrRect(0, 0, w, h), app.ctx)
                    out = np.flipud(px)
                    writer.append_data(out)
                    if frame == int(3.45 * 60):
                        imageio.imwrite(FOLDER / 'gluteus_comparison.png', out)
            print('Exported', FOLDER / 'gluteus_comparison.mp4')
            return
        last = time.perf_counter()
        while not app.glfw.window_should_close(app.window):
            now = time.perf_counter()
            if not app.paused:
                app.phase += min(now - last, 0.1) * app.speed
            last = now
            app.render()
            app.glfw.swap_buffers(app.window)
            app.glfw.poll_events()
            time.sleep(0.005)
    finally:
        app.close()


if __name__ == '__main__':
    main()
