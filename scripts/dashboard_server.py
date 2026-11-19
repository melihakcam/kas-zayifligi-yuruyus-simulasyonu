"""Live gait dashboard: runs the published controller and streams it to a browser page.

One process serves the page (http://127.0.0.1:8765) and a WebSocket on the same
port. The simulation runs in a single worker thread (the OpenGL context is bound
to that thread). Each 20 ms control step sends one JPEG frame and one JSON state
message. Muscle tendons are coloured by their current activation.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import http
import io
import json
from pathlib import Path
import sys
import time
import webbrowser

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_weakness_sweep as sweep  # noqa: E402

PAGE = ROOT / 'scripts/dashboard/index.html'
PORT = 8765
WIDTH, HEIGHT = 960, 720
THRESHOLD = sweep.THRESHOLD
FALL_RATIO = sweep.FALL_RATIO
JOINTS = ['hip_flexion_r', 'knee_angle_r', 'ankle_angle_r']
LOW = np.array([0.22, 0.32, 0.52])     # resting muscle colour
HIGH = np.array([1.0, 0.12, 0.05])     # fully active
WEAK_EDGE = np.array([1.0, 0.62, 0.1])


class Simulation:
    """Owns the env, policy and renderer. Every method runs on the sim thread."""

    def setup(self):
        import gymnasium as gym
        import mujoco
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
        sweep.init_worker()
        from wrapper import MuscleNormWrapper
        self.mj = mujoco
        config = sweep._worker['config']
        self.policy = sweep._worker['policy']
        options = dict(config['single_env_kwargs'])
        options.update(random_init=False, reset_noise_scale=0.0, gait_cycles=3, qpos_diff_th=1e9)
        self.env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
        self.base = self.env.unwrapped
        self.model, self.data = self.base.model, self.base.data
        self.norm = VecNormalize.load(str(ROOT / 'vendor/checkpoints/LocomotionLegs/checkpoint/best_env.zip'),
                                      DummyVecEnv([lambda: self.env]))
        self.norm.training = False
        self.norm.norm_reward = False
        m = self.model
        self.gain = m.actuator_gainprm[:, 2].copy()
        self.tendon = m.actuator_trnid[:, 0].astype(int)
        self.width0 = m.tendon_width.copy()
        self.group_ids = {g: [m.actuator(n).id for n in names] for g, names in sweep.GROUPS.items()}
        self.left_ids = {g: [m.actuator(n[:-2] + '_l').id for n in names if mujoco.mj_name2id(
            m, mujoco.mjtObj.mjOBJ_ACTUATOR, n[:-2] + '_l') >= 0] for g, names in sweep.GROUPS.items()}
        self.qadr = [int(m.jnt_qposadr[m.joint(j).id]) for j in JOINTS]
        self.pelvis = m.body('pelvis').id
        foot = {m.body('calcn_r').id, m.body('toes_r').id}
        self.right_foot_geoms = {i for i in range(m.ngeom) if int(m.geom_bodyid[i]) in foot}
        m.vis.global_.offwidth = max(m.vis.global_.offwidth, WIDTH)
        m.vis.global_.offheight = max(m.vis.global_.offheight, HEIGHT)
        self.renderer = mujoco.Renderer(m, HEIGHT, WIDTH)
        self.option = mujoco.MjvOption()
        self.option.flags[mujoco.mjtVisFlag.mjVIS_TENDON] = True
        self.camera = mujoco.MjvCamera()
        self.view = 'side'
        with np.load(ROOT / 'results/visual_gluteus/normal.npz') as normal:
            self.normal = {k: normal[k].copy() for k in normal.files}
        self.running = False
        self.capacities = {}
        return {'groups': list(sweep.GROUPS), 'joints': JOINTS}

    def start(self, capacities):
        self.capacities = {g: float(np.clip(capacities.get(g, 1.0), 0, 1)) for g in sweep.GROUPS}
        m = self.model
        m.actuator_gainprm[:, 2] = self.gain
        m.tendon_width[:] = self.width0
        self.weak = np.zeros(m.nu, dtype=bool)
        for g, c in self.capacities.items():
            ids = self.group_ids[g]
            m.actuator_gainprm[ids, 2] = self.gain[ids] * c
            if c < 1:
                self.weak[ids] = True
                m.tendon_width[self.tendon[ids]] = 0.009
        self.obs = self.norm.reset()
        self.h0 = float(self.data.xpos[self.pelvis, 2])
        self.step_index = 0
        self.deviated_at = None
        self.fell_at = None
        self.after_fall = 0
        self.running = True
        return self.snapshot('running')

    def step(self):
        if not self.running:
            return None
        action, _ = self.policy.predict(self.obs, deterministic=True)
        self.obs, _, done, _ = self.norm.step(action)
        if done[0]:
            self.running = False
            # The VecEnv has already reset; report the outcome without a new frame.
            status = 'deviated' if self.deviated_at is not None else 'walked'
            return {'state': {'status': status, 'final': True, 'time': self.last_time}}
        self.step_index += 1
        t = float(self.data.time)
        self.last_time = t
        error = float(np.abs(self.data.qpos[3:] - self.base.qpos_ref[3:]).mean())
        if error > THRESHOLD and self.deviated_at is None:
            self.deviated_at = t
        if self.data.xpos[self.pelvis, 2] < FALL_RATIO * self.h0 and self.fell_at is None:
            self.fell_at = t
        status = 'fell' if self.fell_at is not None else ('deviated' if self.deviated_at is not None else 'running')
        if self.fell_at is not None:
            self.after_fall += 1
            if self.after_fall > 50:
                self.running = False
                return self.snapshot('fell', final=True)
        return self.snapshot(status)

    def grf(self):
        """Vertical ground force on the right foot (N)."""
        total = 0.0
        force = np.zeros(6)
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            if c.geom1 in self.right_foot_geoms or c.geom2 in self.right_foot_geoms:
                self.mj.mj_contactForce(self.model, self.data, i, force)
                total += abs(force[0] * c.frame[2])  # normal force projected on world z
        return total

    def snapshot(self, status, final=False):
        m, d = self.model, self.data
        act = d.act.copy()
        color = LOW[None, :] + np.clip(act, 0, 1)[:, None] * (HIGH - LOW)[None, :]
        rgba = np.ones((m.nu, 4))
        rgba[:, :3] = color
        rgba[self.weak, :3] = 0.55 * color[self.weak] + 0.45 * WEAK_EDGE
        m.tendon_rgba[self.tendon] = rgba
        cam = self.camera
        cam.type = self.mj.mjtCamera.mjCAMERA_FREE
        target = d.xpos[self.pelvis].copy()
        if self.view == 'front':
            cam.azimuth, cam.elevation, cam.distance = 180, -10, 3.0
            target[2] = 0.85
        elif self.view == 'foot':
            target = d.xpos[m.body('calcn_r').id].copy()
            target[2] += 0.25
            cam.azimuth, cam.elevation, cam.distance = 90, -12, 1.2
        elif self.view == 'back':
            cam.azimuth, cam.elevation, cam.distance = 0, -12, 3.0
            target[2] = 0.85
        else:
            cam.azimuth, cam.elevation, cam.distance = 90, -12, 3.2
            target[2] = 0.85
        cam.lookat[:] = target
        self.renderer.update_scene(d, camera=cam, scene_option=self.option)
        pixels = self.renderer.render()
        from PIL import Image
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format='JPEG', quality=82)
        k = min(self.step_index, len(self.normal['time']) - 1)
        normal_act = self.normal['act'][k]
        normal_q = self.normal['qpos'][k]
        groups = {g: {'right': float(act[ids].mean()), 'normal': float(normal_act[ids].mean()),
                      'left': float(act[self.left_ids[g]].mean()) if self.left_ids[g] else None}
                  for g, ids in self.group_ids.items()}
        state = {
            'status': status, 'final': final, 'time': float(d.time),
            'cycle': float((d.time % self.base.terminate_time) / self.base.terminate_time * 100),
            'error': float(np.abs(d.qpos[3:] - self.base.qpos_ref[3:]).mean()),
            'pelvis_ratio': float(d.xpos[self.pelvis, 2] / self.h0),
            'joints': {j: {'now': float(np.rad2deg(d.qpos[a])), 'normal': float(np.rad2deg(normal_q[a]))}
                       for j, a in zip(JOINTS, self.qadr)},
            'groups': groups, 'grf': self.grf(),
            'deviated_at': self.deviated_at, 'fell_at': self.fell_at,
            'capacities': self.capacities,
        }
        return {'state': state, 'frame': buffer.getvalue()}

    def set_view(self, view):
        self.view = view
        return self.snapshot('paused') if not self.running and hasattr(self, 'h0') else None


def http_response(body, content_type):
    from websockets.datastructures import Headers
    from websockets.http11 import Response
    return Response(200, 'OK', Headers([('Content-Type', content_type), ('Content-Length', str(len(body))),
                                        ('Cache-Control', 'no-store')]), body)


def sweep_data():
    out = {}
    for name in ('forward_sweep', 'forward_sweep_robust'):
        path = ROOT / 'results' / name / 'sweep.json'
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            out[name] = [{k: r[k] for k in ('groups', 'remaining_active_capacity', 'outcome',
                                             'max_mean_coordinate_error_rad', 'seed') if k in r}
                         for r in data['results']]
    return out


async def main():
    from websockets.asyncio.server import serve
    sim = Simulation()
    pool = ThreadPoolExecutor(1)
    loop = asyncio.get_running_loop()
    print('Model ve kontrolcu yukleniyor (yaklasik 30 sn)...', flush=True)
    info = await loop.run_in_executor(pool, sim.setup)
    clients = set()
    control = {'speed': 1.0, 'paused': False}

    async def broadcast(message):
        if message is None:
            return
        frame = message.get('frame')
        text = json.dumps({'type': 'state', **message['state']})
        for ws in list(clients):
            try:
                await ws.send(text)
                if frame:
                    await ws.send(frame)
            except Exception:
                clients.discard(ws)

    async def runner():
        while True:
            if sim.running and not control['paused'] and clients:
                began = time.perf_counter()
                await broadcast(await loop.run_in_executor(pool, sim.step))
                wait = 0.02 / control['speed'] - (time.perf_counter() - began)
                await asyncio.sleep(max(0.0, wait))
            else:
                await asyncio.sleep(0.05)

    async def handler(ws):
        clients.add(ws)
        await ws.send(json.dumps({'type': 'info', **info}))
        try:
            async for raw in ws:
                msg = json.loads(raw)
                cmd = msg.get('cmd')
                if cmd == 'start':
                    control['paused'] = False
                    await broadcast(await loop.run_in_executor(pool, sim.start, msg.get('capacities', {})))
                elif cmd == 'pause':
                    control['paused'] = bool(msg.get('paused', not control['paused']))
                elif cmd == 'speed':
                    control['speed'] = float(np.clip(msg.get('value', 1.0), 0.1, 2.0))
                elif cmd == 'view':
                    await broadcast(await loop.run_in_executor(pool, sim.set_view, msg.get('value', 'side')))
        finally:
            clients.discard(ws)

    def process_request(connection, request):
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            return None
        if request.path.startswith('/api/sweep'):
            return http_response(json.dumps(sweep_data()).encode(), 'application/json')
        return http_response(PAGE.read_bytes(), 'text/html; charset=utf-8')

    async with serve(handler, '127.0.0.1', PORT, process_request=process_request, max_size=None):
        url = f'http://127.0.0.1:{PORT}'
        print(f'Hazir: {url}  (kapatmak icin bu pencereyi kapatin)', flush=True)
        webbrowser.open(url)
        await runner()


if __name__ == '__main__':
    asyncio.run(main())
