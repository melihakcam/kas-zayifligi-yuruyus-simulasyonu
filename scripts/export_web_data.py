"""Export recorded walks for the browser viewer (web/).

For each scenario the published (or adapted) controller walks the model and
every control step (20 ms) is stored: bone poses, muscle paths resampled to a
fixed number of points, activation, muscle force, vertical ground reaction
force under each foot, pelvis height and joint tracking error. Bone meshes are
exported once. Everything goes to <out>/manifest.json, meshes.bin and one
<scenario>.bin per scenario (little-endian float32 / uint32).

  python scripts/export_web_data.py --adapted results/adaptation/glut_med_max_020 --out web/data
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_weakness_sweep as sweep  # noqa: E402

POINTS = 8            # samples along each muscle path
AFTER_FALL = 40       # control steps kept after a fall, for the animation
BOTH = ('right_gluteus_medius', 'right_gluteus_maximus')
SCENARIOS = [
    # key, label, groups, capacity, controller, seed, noise
    ('normal', 'Normal yürüyüş', (), 1.0, 'original', 0, 0.0),
    ('glmed', 'Sadece gluteus medius %20', ('right_gluteus_medius',), 0.2, 'original', 0, 0.0),
    ('glmax', 'Sadece gluteus maksimus %20', ('right_gluteus_maximus',), 0.2, 'original', 0, 0.0),
    ('both', 'İkisi birlikte %20', BOTH, 0.2, 'original', 0, 0.0),
    ('both_adapted', 'İkisi birlikte %20 + alışmış kontrolcü', BOTH, 0.2, 'adapted', 0, 0.001),
]
GROUP_LABELS = {
    'tibialis_anterior': 'Tibialis anterior', 'soleus': 'Soleus', 'gastrocnemius': 'Gastroknemius',
    'vasti': 'Vastuslar (kuadriseps)', 'hamstrings': 'Hamstring', 'gluteus_medius': 'Gluteus medius',
    'gluteus_maximus': 'Gluteus maksimus', 'hip_flexors': 'Kalça fleksörleri (iliopsoas)',
}


def resample(points, count):
    if len(points) == 1:
        return np.repeat(points, count, axis=0)
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] <= 0:
        return np.repeat(points[:1], count, axis=0)
    target = np.linspace(0, s[-1], count)
    return np.stack([np.interp(target, s, points[:, k]) for k in range(3)], axis=1)


def load_policy(kind, adapted):
    from DynSyn import SAC_DynSyn
    checkpoint = ROOT / 'vendor/checkpoints/LocomotionLegs/checkpoint'
    model_path, env_path = ((checkpoint / 'best_model.zip', checkpoint / 'best_env.zip') if kind == 'original'
                            else (adapted / 'final_model.zip', adapted / 'final_env.zip'))
    policy = SAC_DynSyn.load(str(model_path), device='cpu', custom_objects=sweep.INFERENCE_OBJECTS)
    return policy, env_path


def record(scenario, adapted):
    import gymnasium as gym
    import mujoco
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from wrapper import MuscleNormWrapper

    key, label, groups, capacity, kind, seed, noise = scenario
    config = sweep._worker['config']
    policy, env_path = load_policy(kind, adapted)
    options = dict(config['single_env_kwargs'])
    options.update(random_init=False, reset_noise_scale=noise, gait_cycles=3, qpos_diff_th=1e9)
    env = MuscleNormWrapper(gym.make(config['env_name'], render_mode=None, **options))
    base = env.unwrapped
    model, data = base.model, base.data
    norm = VecNormalize.load(str(env_path), DummyVecEnv([lambda: env]))
    norm.training = False
    norm.norm_reward = False
    full_force = model.actuator_gainprm[:, 2].copy()
    ids = [model.actuator(m).id for g in groups for m in sweep.GROUPS[g]]
    model.actuator_gainprm[ids, 2] *= capacity
    if noise > 0:
        norm.seed(seed)
    obs = norm.reset()

    geoms = [g for g in range(model.ngeom)
             if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH and model.geom_group[g] < 3]
    muscles = list(range(model.nu))
    tendons = [int(model.actuator_trnid[a, 0]) for a in muscles]
    act_index = model.actuator_actadr[muscles]
    feet = {side: {model.body(f'calcn_{side}').id, model.body(f'toes_{side}').id} for side in 'rl'}
    pelvis = model.body('pelvis').id
    h0 = float(data.xpos[pelvis, 2])
    frames = {k: [] for k in ('time', 'geom_pos', 'geom_quat', 'paths', 'act', 'force',
                              'grf', 'foot', 'pelvis_h', 'error')}
    quat = np.zeros(4)
    force6 = np.zeros(6)

    def keep():
        frames['time'].append(data.time)
        frames['geom_pos'].append(data.geom_xpos[geoms].copy())
        qs = []
        for g in geoms:
            mujoco.mju_mat2Quat(quat, data.geom_xmat[g])
            qs.append(quat.copy())
        frames['geom_quat'].append(np.asarray(qs))
        wrap_xpos = data.wrap_xpos.reshape(-1, 3)
        wrap_obj = data.wrap_obj.reshape(-1)
        paths = []
        for t in tendons:
            adr, num = int(data.ten_wrapadr[t]), int(data.ten_wrapnum[t])
            pts = wrap_xpos[adr:adr + num][wrap_obj[adr:adr + num] != -2]
            paths.append(resample(pts, POINTS) if len(pts) else np.zeros((POINTS, 3)))
        frames['paths'].append(np.asarray(paths))
        frames['act'].append(data.act[act_index].copy())
        frames['force'].append(np.abs(data.actuator_force[muscles]))
        grf = [0.0, 0.0]
        for i in range(data.ncon):
            c = data.contact[i]
            bodies = {int(model.geom_bodyid[c.geom1]), int(model.geom_bodyid[c.geom2])}
            for j, side in enumerate('rl'):
                if bodies & feet[side]:
                    mujoco.mj_contactForce(model, data, i, force6)
                    grf[j] += abs(force6[0])
        frames['grf'].append(grf)
        frames['foot'].append([data.xpos[model.body(f'calcn_{s}').id].copy() for s in 'rl'])
        frames['pelvis_h'].append(data.xpos[pelvis, 2])
        frames['error'].append(np.abs(data.qpos[3:] - base.qpos_ref[3:]).mean())

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
        elif data.xpos[pelvis, 2] < sweep.FALL_RATIO * h0:
            fell_at, extra = float(data.time), AFTER_FALL
    norm.close()
    arrays = {k: np.asarray(v, dtype=np.float32) for k, v in frames.items()}
    errors = arrays['error'][: len(arrays['error']) if fell_at is None else
                             int(np.searchsorted(arrays['time'], fell_at)) + 1]
    outcome = 'fell' if fell_at is not None else ('deviated' if (errors > sweep.THRESHOLD).any() else 'walked')
    info = {'key': key, 'label': label, 'groups': list(groups), 'capacity': capacity, 'controller': kind,
            'seed': seed, 'reset_noise_scale': noise, 'outcome': outcome, 'fell_at_s': fell_at,
            'frames': int(len(arrays['time']))}
    return info, arrays, (model, geoms, muscles, full_force)


def export_meshes(model, geoms, out, reduction):
    try:
        import fast_simplification
    except ImportError:
        fast_simplification = None
    used = sorted({int(model.geom_dataid[g]) for g in geoms})
    blob, meshes = bytearray(), {}
    for m in used:
        v0, nv = int(model.mesh_vertadr[m]), int(model.mesh_vertnum[m])
        f0, nf = int(model.mesh_faceadr[m]), int(model.mesh_facenum[m])
        verts = model.mesh_vert[v0:v0 + nv].astype(np.float32)
        faces = model.mesh_face[f0:f0 + nf].astype(np.int64)
        if fast_simplification is not None and nf > 400 and reduction > 0:
            verts, faces = fast_simplification.simplify(verts, faces, target_reduction=reduction)
            verts, faces = verts.astype(np.float32), faces.astype(np.int64)
        entry = {'vert_offset': len(blob), 'vert_count': int(len(verts))}
        blob += verts.tobytes()
        entry.update(face_offset=len(blob), face_count=int(len(faces)))
        blob += faces.astype(np.uint32).tobytes()
        meshes[m] = entry
    (out / 'meshes.bin').write_bytes(bytes(blob))
    order = {m: i for i, m in enumerate(used)}
    return ([meshes[m] for m in used],
            [{'mesh': order[int(model.geom_dataid[g])], 'body': model.body(int(model.geom_bodyid[g])).name,
              'rgba': [round(float(x), 3) for x in model.geom_rgba[g]]} for g in geoms])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapted', required=True, help='folder with final_model.zip / final_env.zip')
    parser.add_argument('--out', default='web/data')
    parser.add_argument('--eval-original', help='eval_original.json (summary counts)')
    parser.add_argument('--eval-adapted', help='eval_final.json (summary counts)')
    parser.add_argument('--mesh-reduction', type=float, default=0.6)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    adapted = Path(args.adapted)
    sweep.init_worker()

    layout = ['time', 'geom_pos', 'geom_quat', 'paths', 'act', 'force', 'grf', 'foot', 'pelvis_h', 'error']
    scenarios, model_info = [], None
    for scenario in SCENARIOS:
        info, arrays, model_info = record(scenario, adapted)
        blob = bytearray()
        info['arrays'] = {}
        for name in layout:
            a = np.ascontiguousarray(arrays[name], dtype=np.float32)
            info['arrays'][name] = {'offset': len(blob), 'shape': list(a.shape)}
            blob += a.tobytes()
        (out / f"{info['key']}.bin").write_bytes(bytes(blob))
        scenarios.append(info)
        print(info['key'], info['outcome'], info['fell_at_s'], info['frames'], 'frames', flush=True)

    model, geoms, muscles, full_force = model_info
    meshes, geom_info = export_meshes(model, geoms, out, args.mesh_reduction)
    group_of = {}
    for g, names in sweep.GROUPS.items():
        short = g.replace('right_', '')
        for m in names:
            group_of[m] = short
            group_of[m[:-2] + '_l'] = short
    muscle_info = []
    for a in muscles:
        name = model.actuator(a).name
        muscle_info.append({'name': name, 'side': name[-1], 'group': group_of.get(name, 'other'),
                            'max_force': round(float(full_force[a]), 1),
                            'tau_act': round(float(model.actuator_dynprm[a, 0]), 4),
                            'tau_deact': round(float(model.actuator_dynprm[a, 1]), 4)})
    evals = {}
    for kind, path in (('original', args.eval_original), ('adapted', args.eval_adapted)):
        if path and Path(path).exists():
            evals[kind] = json.loads(Path(path).read_text())['summary']
    manifest = {'dt': float(model.opt.timestep) * 10, 'points_per_muscle': POINTS,
                'threshold_rad': sweep.THRESHOLD, 'fall_ratio': sweep.FALL_RATIO,
                'groups': {k: v for k, v in GROUP_LABELS.items()}, 'muscles': muscle_info,
                'meshes': meshes, 'geoms': geom_info, 'scenarios': scenarios, 'layout': layout,
                'evaluation': evals}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    sizes = {p.name: round(p.stat().st_size / 1e6, 2) for p in out.iterdir()}
    print(json.dumps(sizes, indent=1))


if __name__ == '__main__':
    main()
