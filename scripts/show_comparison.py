"""Local side-by-side viewer of forward simulation and fixed-motion analysis."""
import argparse
import json
from pathlib import Path
import time

import glfw
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'results/visual_comparison'


def load(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key].copy() for key in data.files}


class Comparison:
    def __init__(self, hidden=False):
        self.normal = load(FOLDER / 'normal.npz')
        self.weak = load(FOLDER / 'weak.npz')
        self.target = load(ROOT / 'results/baseline/trajectory.npz')
        self.analysis = load(ROOT / 'results/temporal_margin/0.40_rate_1.0.npz')
        self.report = json.loads((FOLDER / 'summary.json').read_text())
        self.margin = json.loads((ROOT / 'results/temporal_margin/margin.json').read_text())
        self.models = [mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml')) for _ in range(2)]
        self.data = [mujoco.MjData(model) for model in self.models]
        self.cameras = [mujoco.MjvCamera() for _ in range(2)]
        self.scenes = [mujoco.MjvScene(model, maxgeom=20000) for model in self.models]
        self.options = mujoco.MjvOption()
        self.options.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = True
        for side, model in enumerate(self.models):
            model.vis.quality.shadowsize = 1024
            aid = model.actuator('tibant_r').id
            tid = int(model.actuator_trnid[aid, 0])
            model.tendon_rgba[tid] = (0.1, 0.85, 0.5, 1) if side == 0 else (1, 0.45, 0.05, 1)
            model.tendon_width[tid] = 0.008
            if side == 1:
                model.actuator_gainprm[aid, 2] *= 0.4
        if not glfw.init():
            raise RuntimeError('GLFW could not initialize')
        glfw.window_hint(glfw.VISIBLE, not hidden)
        self.window = glfw.create_window(1280, 720, 'Kas karsilastirmasi - normal / %40 kuvvet', None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError('Could not open comparison window')
        glfw.make_context_current(self.window)
        glfw.swap_interval(1 if not hidden else 0)
        self.context = mujoco.MjrContext(self.models[0], mujoco.mjtFontScale.mjFONTSCALE_150)
        self.paused = False
        self.zoom = False
        self.mode = 0
        self.speed = 0.5
        self.phase = 0.0
        glfw.set_key_callback(self.window, self.key)

    def key(self, window, key, scan, action, mods):
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_SPACE:
            self.paused = not self.paused
        elif key == glfw.KEY_TAB:
            self.mode = 1 - self.mode
            self.phase = 0
        elif key == glfw.KEY_Z:
            self.zoom = not self.zoom
        elif key == glfw.KEY_R:
            self.phase = 0
        elif key == glfw.KEY_1:
            self.speed = 0.25
        elif key == glfw.KEY_2:
            self.speed = 0.5
        elif key == glfw.KEY_3:
            self.speed = 1.0

    def overlay(self, viewport, position, text, values=''):
        mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_100, position,
                            viewport, text, values, self.context)

    def render(self):
        width, height = glfw.get_framebuffer_size(self.window)
        bar = 48
        span = max(float(self.normal['time'][-1]), float(self.weak['time'][-1])) + 0.002 if self.mode == 0 else 1.17
        phase = self.phase % span
        frames = []
        for side, (model, data) in enumerate(zip(self.models, self.data)):
            source = (self.normal if side == 0 else self.weak) if self.mode == 0 else self.target
            at = phase if self.mode == 0 else 1.17 + phase
            index = max(0, min(len(source['time']) - 1, int(np.searchsorted(source['time'], at, side='right')) - 1))
            data.qpos[:] = source['qpos'][index]
            data.qvel[:] = source['qvel'][index]
            data.act[:] = source['activation'][index]
            data.ctrl[:] = source['ctrl'][index]
            data.time = source['time'][index]
            mujoco.mj_forward(model, data)
            frames.append((source, index))
            camera = self.cameras[side]
            camera.type = mujoco.mjtCamera.mjCAMERA_FREE
            camera.azimuth = 90
            camera.elevation = -12 if self.zoom else -15
            camera.distance = 1.1 if self.zoom else 3.4
            camera.lookat[:] = data.xpos[model.body('calcn_r' if self.zoom else 'pelvis').id]
            camera.lookat[2] += 0.22 if self.zoom else 0.1
            mujoco.mjv_updateScene(model, data, self.options, None, camera,
                                   mujoco.mjtCatBit.mjCAT_ALL, self.scenes[side])
            viewport = mujoco.MjrRect(side * (width // 2), bar, width // 2, height - bar)
            mujoco.mjr_render(viewport, self.scenes[side], self.context)
            title = 'NORMAL | Kuvvet %100' if side == 0 else 'ZAYIF | Sag on kaval kasi %40'
            subtitle = 'Fizik simulasyonu kaydi' if self.mode == 0 else 'HEDEF HAREKET SABIT | Tork analizi'
            if side == 1:
                if self.mode == 0:
                    left, il = frames[0]
                    delta = abs(np.rad2deg(left['ankle_angle'][il] - source['ankle_angle'][index]))
                    subtitle += f'\nAyak bilegi farki: {delta:.1f} derece'
                else:
                    subtitle += '\nTork siniri bir yurumeme kaniti degildir'
            self.overlay(viewport, mujoco.mjtGridPos.mjGRID_TOPLEFT, title + '\n' + subtitle)
            if self.mode == 0:
                source, index = frames[side]
                finished = at > float(source['time'][-1]) + 0.002
                status = 'Kayit sona erdi; son kare' if finished else 'Ayni hazir yurutucu, yeniden egitim yok'
                self.overlay(viewport, mujoco.mjtGridPos.mjGRID_BOTTOMLEFT,
                             f'{status}\nSure: {min(at, float(source["time"][-1])):.2f} s')
            else:
                index_a = min(len(self.analysis['activation']) - 1, int(round(phase / 0.002)))
                error = float(np.abs(self.analysis['delivered_torque'][index_a] - self.analysis['target_torque'][index_a]).max())
                text = ('Normal yuruyus hedefi\nDiger tarafta da ayni hareket gosteriliyor' if side == 0 else
                        f'Ornek sinirli cozumde anlik tork hatasi: {error:.2f} Nm\nTum dongude gerekli en buyuk hata en az: 4.21 Nm')
                self.overlay(viewport, mujoco.mjtGridPos.mjGRID_BOTTOMLEFT, text)
        mujoco.mjr_label(mujoco.MjrRect(0, 0, width, bar), mujoco.mjtFont.mjFONT_NORMAL,
                         f'SPACE: durdur | Z: ayaga yakinlas | TAB: gorunum | 1/2/3: hiz | R: bastan | ESC: kapat | Hiz: {self.speed:g}x',
                         0.12, 0.12, 0.12, 1, 0.92, 0.92, 0.92, self.context)
        return width, height

    def close(self):
        self.context.free()
        glfw.destroy_window(self.window)
        glfw.terminate()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', action='store_true', help='Render a side-by-side MP4 and previews')
    args = parser.parse_args()
    app = Comparison(hidden=args.export)
    try:
        if args.export:
            import imageio.v2 as imageio
            for mode, name in ((0, 'physical_comparison'), (1, 'fixed_motion_analysis')):
                app.mode = mode
                duration = 3.52 if mode == 0 else 1.17
                # Half speed gives time to inspect the actual simulation response.
                with imageio.get_writer(FOLDER / f'{name}.mp4', fps=30, codec='libx264') as writer:
                    count = int(np.ceil(duration * 60))
                    for frame in range(count):
                        app.phase = min(duration - 0.002, frame / 60)
                        width, height = app.render()
                        pixels = np.empty((height, width, 3), dtype=np.uint8)
                        mujoco.mjr_readPixels(pixels, None, mujoco.MjrRect(0, 0, width, height), app.context)
                        output = np.flipud(pixels)
                        writer.append_data(output)
                        if frame == count // 2:
                            imageio.imwrite(FOLDER / f'{name}.png', output)
                    print(f'Exported {name}', flush=True)
            return
        last = time.perf_counter()
        while not glfw.window_should_close(app.window):
            now = time.perf_counter()
            if not app.paused:
                app.phase += min(now - last, 0.1) * app.speed
            last = now
            app.render()
            glfw.swap_buffers(app.window)
            glfw.poll_events()
            time.sleep(0.005)
    finally:
        app.close()


if __name__ == '__main__':
    main()
