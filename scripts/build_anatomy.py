"""Fit the Z-Anatomy model onto the MS-Human-700 skeleton and skin its muscles.

Inputs
  web/build/za_raw.json/.bin          Z-Anatomy meshes (scripts/blender/export_zanatomy.py)
  web/build/rest_model.txt, rest_data.txt   MS-Human rest pose (scripts/mujoco_rest_pose.py)
  web/data/manifest.json, meshes.bin  MS-Human bone meshes and recorded walks (export_web_data.py)

Steps
  1. Every Z-Anatomy bone is assigned to an MS-Human body (femur -> femur_r, ...).
  2. For each body a similarity transform (scale, rotation, translation) is fitted with
     ICP so the Z-Anatomy bones sit on the MS-Human bone meshes in the rest pose.
  3. Every muscle vertex gets skin weights from its distance to the bones of each body,
     and is carried into the MS-Human rest pose with the blended body transforms.
  4. Output web/data/anatomy.json + anatomy.bin for the browser (linear blend skinning,
     driven by the recorded MS-Human body poses).

  python scripts/build_anatomy.py
"""
import json
from pathlib import Path
import re

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
BUILD, DATA = ROOT / 'web/build', ROOT / 'web/data'
SIGMA = 0.018          # m, width of the skin-weight falloff between neighbouring bones
MAX_INFLUENCES = 4

MS_TO_ZA = {
    'addbrev': 'Adductor brevis', 'addlong': 'Adductor longus', 'addmag': 'Adductor magnus',
    'bflh': 'Long head of biceps femoris', 'bfsh': 'Short head of biceps femoris',
    'edl': 'Extensor digitorum longus', 'ehl': 'Extensor hallucis longus',
    'fdl': 'Flexor digitorum longus', 'fhl': 'Flexor hallucis longus',
    'gaslat': 'Lateral head of gastrocnemius', 'gasmed': 'Medial head of gastrocnemius',
    'glmax': 'Gluteus maximus muscle', 'glmed': 'Gluteus medius muscle', 'glmin': 'Gluteus minimus muscle',
    'grac': 'Gracilis muscle', 'iliacus': 'Iliacus muscle', 'perbrev': 'Fibularis brevis muscle',
    'perlong': 'Fibularis longus muscle', 'piri': 'Piriformis muscle', 'recfem': 'Rectus femoris muscle',
    'sart': 'Sartorius muscle', 'semimem': 'Semimembranosus muscle', 'semiten': 'Semitendinosus muscle',
    'soleus': 'Soleus muscle', 'tfl': 'Tensor fasciae latae', 'tibant': 'Tibialis anterior muscle',
    'tibpost': 'Tibialis posterior muscle', 'vasint': 'Vastus intermedius muscle',
    'vaslat': 'Vastus lateralis muscle', 'vasmed': 'Vastus medialis muscle', 'Ps': 'Psoas major',
}
GROUP_OF = {
    'Gluteus medius muscle': 'gluteus_medius', 'Gluteus maximus muscle': 'gluteus_maximus',
    'Iliacus muscle': 'hip_flexors', 'Psoas major': 'hip_flexors',
    'Long head of biceps femoris': 'hamstrings', 'Short head of biceps femoris': 'hamstrings',
    'Semimembranosus muscle': 'hamstrings', 'Semitendinosus muscle': 'hamstrings',
    'Vastus intermedius muscle': 'vasti', 'Vastus lateralis muscle': 'vasti', 'Vastus medialis muscle': 'vasti',
    'Lateral head of gastrocnemius': 'gastrocnemius', 'Medial head of gastrocnemius': 'gastrocnemius',
    'Soleus muscle': 'soleus', 'Tibialis anterior muscle': 'tibialis_anterior',
}
ORDINAL = {w: i + 1 for i, w in enumerate(['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh',
                                           'Eighth', 'Ninth', 'Tenth', 'Eleventh', 'Twelfth'])}
ORD_LOWER = {k.lower(): v for k, v in ORDINAL.items()}


def body_for_bone(name):
    """Z-Anatomy bone name -> MS-Human body name (None: not used)."""
    side = name[-1] if name.endswith(('.l', '.r')) else None
    base = name[:-2] if side else name
    s = side or ''
    limb = {'Femur': 'femur', 'Patella': 'patella', 'Tibia': 'tibia', 'Fibula': 'tibia', 'Talus': 'talus',
            'Calcaneus': 'calcn', 'Clavicle': 'clavicle', 'Scapula': 'scapula', 'Humerus': 'humerus',
            'Radius': 'radius', 'Ulna': 'ulna'}
    if base in limb:
        return f'{limb[base]}_{s}'
    if base == 'Hip bone':
        return 'pelvis'
    if base in ('Sacrum', 'Coccyx'):
        return 'sacrum'
    if base in ('Body of sternum', 'Manubrium of sternum', 'Xiphoid process'):
        return 'sternum'
    m = re.match(r'Vertebra ([LTC])(\d+)', base)
    if m:
        kind, n = m.group(1), int(m.group(2))
        return {'L': f'lumbar{n}', 'T': f'thoracic{n}', 'C': 'head_neck'}[kind]
    if base in ('Atlas (C1)', 'Axis (C2)'):
        return 'head_neck'
    m = re.match(r'(\w+) rib$', base)
    if m and m.group(1) in ORDINAL:
        return f'rib{ORDINAL[m.group(1)]}_{s.upper()}'
    m = re.match(r'Costal cartilage of (\w+) rib', base)
    if m and m.group(1) in ORD_LOWER:
        return f'rib{ORD_LOWER[m.group(1)]}_{s.upper()}'
    if base in ('Navicular bone', 'Cuboid bone', 'Sesamoid bones of foot') or 'cuneiform' in base \
            or 'metatarsal' in base:
        return f'calcn_{s}'
    if 'finger of foot' in base:
        return f'toes_{s}'
    if base in ('Scaphoid bone', 'Lunate bone', 'Triquetrum bone', 'Pisiform bone'):
        return f'proximal_row_{s}'
    if base in ('Trapezium bone', 'Trapezoid bone', 'Capitate bone', 'Hamate bone') or 'metacarpal' in base \
            or 'finger of hand' in base:
        return f'hand_{s}'
    return 'head_neck' if side is None or base in ('Temporal bone', 'Parietal bone', 'Maxilla', 'Zygomatic bone',
                                                    'Nasal bone', 'Lacrimal bone', 'Palatine bone',
                                                    'Inferior nasal concha bone') else None


# ---------------------------------------------------------------- MuJoCo text dumps
def parse_model(path):
    blocks, current = {'BODY': {}, 'GEOM': {}}, None
    for line in path.read_text().splitlines():
        m = re.match(r'^(BODY|GEOM) (\d+):', line)
        if m:
            current = blocks[m.group(1)].setdefault(int(m.group(2)), {})
            continue
        if not line.strip():
            current = None
            continue
        if current is not None:
            key, *vals = line.split()
            current[key] = vals
    return blocks


def parse_data(path, names):
    out, lines = {}, path.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.strip() in names:
            rows = []
            for row in lines[i + 1:]:
                if not row.strip() or re.match(r'^[A-Z_]', row):
                    break
                rows.append([float(x) for x in row.split()])
            out[line.strip()] = np.array(rows)
    return out


def quat_to_mat(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------- registration
def umeyama(src, dst):
    ms, md = src.mean(0), dst.mean(0)
    x, y = src - ms, dst - md
    cov = y.T @ x / len(src)
    u, s, vt = np.linalg.svd(cov)
    d = np.eye(3)
    d[2, 2] = np.sign(np.linalg.det(u) * np.linalg.det(vt))
    r = u @ d @ vt
    scale = np.trace(np.diag(s) @ d) / (x ** 2).sum(1).mean()
    return scale, r, md - scale * r @ ms


def icp(src, dst, iterations=60):
    tree_d = cKDTree(dst)
    s, r, t = 1.0, np.eye(3), dst.mean(0) - src.mean(0)
    for _ in range(iterations):
        moved = s * src @ r.T + t
        dist, idx = tree_d.query(moved)
        keep = dist <= np.quantile(dist, 0.85)
        back_d, back_i = cKDTree(moved).query(dst)
        keep_b = back_d <= np.quantile(back_d, 0.85)
        a = np.vstack([src[keep], src[back_i[keep_b]]])
        b = np.vstack([dst[idx[keep]], dst[keep_b]])
        s, r, t = umeyama(a, b)
        s = float(np.clip(s, 0.85, 1.2))
        t = b.mean(0) - s * r @ a.mean(0)
    moved = s * src @ r.T + t
    return s, r, t, float(np.median(tree_d.query(moved)[0]))


def main():
    manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    ms_mesh = (DATA / 'meshes.bin').read_bytes()
    model = parse_model(BUILD / 'rest_model.txt')
    data = parse_data(BUILD / 'rest_data.txt', {'XPOS', 'XQUAT', 'GEOM_XPOS', 'GEOM_XMAT'})
    body_names = {i: b['name'][0] for i, b in model['BODY'].items()}
    body_id = {n: i for i, n in body_names.items()}
    mesh_geoms = [g for g in sorted(model['GEOM']) if int(model['GEOM'][g]['geom_type'][0]) == 7
                  and int(model['GEOM'][g]['geom_group'][0]) < 3]
    if len(mesh_geoms) != len(manifest['geoms']):
        raise ValueError('Geom list does not match the exported walk data')
    for gid, info in zip(mesh_geoms, manifest['geoms']):
        if body_names[int(model['GEOM'][gid]['geom_bodyid'][0])] != info['body']:
            raise ValueError('Geom order differs from the exported walk data')

    # MS-Human rest-pose bone vertices per body
    ms_verts = {}
    first_geom = {}
    for i, (gid, info) in enumerate(zip(mesh_geoms, manifest['geoms'])):
        mesh = manifest['meshes'][info['mesh']]
        v = np.frombuffer(ms_mesh, np.float32, mesh['vert_count'] * 3, mesh['vert_offset']).reshape(-1, 3)
        rot = data['GEOM_XMAT'][gid].reshape(3, 3)
        ms_verts.setdefault(info['body'], []).append(v @ rot.T + data['GEOM_XPOS'][gid])
        first_geom.setdefault(info['body'], (i, gid))
    ms_verts = {b: np.vstack(v) for b, v in ms_verts.items()}

    # Z-Anatomy meshes, converted to MuJoCo axes: (x, y, z)_mj = (-y, x, z)_za
    rows = json.loads((BUILD / 'za_raw.json').read_text(encoding='utf-8'))
    raw = (BUILD / 'za_raw.bin').read_bytes()
    for r in rows:
        p = np.frombuffer(raw, np.float32, r['vert_count'] * 3, r['pos']).reshape(-1, 3)
        r['v'] = np.stack([-p[:, 1], p[:, 0], p[:, 2]], 1).astype(np.float64)
        r['f'] = np.frombuffer(raw, np.uint32, r['tri_count'] * 3, r['tri']).reshape(-1, 3)
        r['m'] = np.frombuffer(raw, np.uint8, r['tri_count'], r['mat'])

    # mirrored objects (most left-side parts) come with inverted triangle winding
    for r in rows:
        v, f = r['v'], r['f']
        volume = np.einsum('ij,ij->i', v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()
        if volume < 0:
            r['f'] = f[:, ::-1].copy()

    bones = [r for r in rows if r['kind'] == 'bone']
    for r in bones:
        r['body'] = body_for_bone(r['name'])
    bones = [r for r in bones if r['body'] in ms_verts]
    za_bone = {}
    for r in bones:
        za_bone.setdefault(r['body'], []).append(r['v'])
    za_bone = {b: np.vstack(v) for b, v in za_bone.items()}

    # whole-model alignment first (the two models stand at different heights)
    shift = np.median(np.vstack([ms_verts[b] for b in ('pelvis', 'femur_r', 'femur_l')]), 0) - \
        np.median(np.vstack([za_bone[b] for b in ('pelvis', 'femur_r', 'femur_l')]), 0)
    for r in rows:
        r['v'] += shift
    za_bone = {b: v + shift for b, v in za_bone.items()}

    fits, report = {}, {}
    for b in sorted(za_bone):
        s, rot, t, err = icp(za_bone[b], ms_verts[b])
        fits[b] = (s, rot, t)
        report[b] = {'scale': round(s, 3), 'median_gap_mm': round(err * 1000, 1)}
    skin_bodies = sorted(fits, key=lambda b: body_id[b])
    index_of = {b: i for i, b in enumerate(skin_bodies)}
    trees = {b: cKDTree(za_bone[b]) for b in skin_bodies}

    def transform(v, b):
        s, rot, t = fits[b]
        return s * v @ rot.T + t

    # muscles: weights from distance to each body's bones
    muscle_names = [m['name'] for m in manifest['muscles']]
    objects, blob = [], bytearray()

    def emit(name, kind, v, f, m_tendon, weights_idx, weights_val, extra):
        order = np.argsort(m_tendon, kind='stable')
        f = f[order]
        belly = int((m_tendon == 0).sum())
        entry = {'name': name, 'kind': kind, 'verts': int(len(v)), 'tris': int(len(f)), 'belly_tris': belly}
        entry.update(extra)
        entry['pos'] = len(blob); blob.extend(v.astype(np.float32).tobytes())
        entry['skin_index'] = len(blob); blob.extend(weights_idx.astype(np.uint8).tobytes())
        entry['skin_weight'] = len(blob); blob.extend(weights_val.astype(np.uint8).tobytes())
        entry['index'] = len(blob); blob.extend(f.astype(np.uint16).tobytes())
        blob.extend(b'\0' * ((-len(blob)) % 4))
        objects.append(entry)

    for r in rows:
        if r['kind'] != 'muscle':
            continue
        v = r['v']
        dist = np.stack([trees[b].query(v)[0] for b in skin_bodies], 1)
        near = np.argsort(dist, 1)[:, :MAX_INFLUENCES]
        dn = np.take_along_axis(dist, near, 1)
        w = np.exp(-((dn - dn[:, :1]) / SIGMA) ** 2)
        w[w < 0.04] = 0
        w /= w.sum(1, keepdims=True)
        moved = np.zeros_like(v)
        for k in range(MAX_INFLUENCES):
            for j in np.unique(near[:, k]):
                sel = (near[:, k] == j) & (w[:, k] > 0)
                if sel.any():
                    moved[sel] += w[sel, k:k + 1] * transform(v[sel], skin_bodies[j])
        wq = np.round(w * 255).astype(np.int32)
        wq[:, 0] += 255 - wq.sum(1)
        tendon_slot = r['materials'].index('Tendon') if 'Tendon' in r['materials'] else -1
        tendon = (r['m'] == tendon_slot).astype(np.uint8)
        base, side = r['name'][:-2], r['name'][-1]
        drivers = [i for i, n in enumerate(muscle_names)
                   if n.endswith('_' + side) and any(n.startswith(k) and z == base for k, z in MS_TO_ZA.items())]
        emit(r['name'], 'muscle', moved, r['f'], tendon, near, wq,
             {'base': base, 'side': side, 'group': GROUP_OF.get(base, 'other'), 'parent': r['parent'],
              'drivers': drivers})

    # bones: rigid, merged per body
    for b in skin_bodies:
        parts = [r for r in bones if r['body'] == b]
        offset, vs, fs = 0, [], []
        for r in parts:
            vs.append(transform(r['v'], b))
            fs.append(r['f'] + offset)
            offset += len(r['v'])
        v, f = np.vstack(vs), np.vstack(fs)
        if len(v) > 65535:
            raise ValueError(f'too many vertices for one bone mesh: {b}')
        idx = np.zeros((len(v), MAX_INFLUENCES), np.uint8)
        idx[:, 0] = index_of[b]
        wq = np.zeros((len(v), MAX_INFLUENCES), np.uint8)
        wq[:, 0] = 255
        emit(b, 'bone', v, f, np.zeros(len(f), np.uint8), idx, wq, {'parts': [r['name'] for r in parts]})

    skeleton = []
    for b in skin_bodies:
        i, gid = first_geom[b]
        bid = body_id[b]
        g = model['GEOM'][gid]
        skeleton.append({'body': b, 'geom': i,
                         'geom_local_pos': [float(x) for x in g['geom_pos']],
                         'geom_local_quat': [float(x) for x in g['geom_quat']],
                         'rest_pos': data['XPOS'][bid].tolist(), 'rest_quat': data['XQUAT'][bid].tolist()})
    out = {'skeleton': skeleton, 'objects': objects, 'fit': report,
           'source': 'Z-Anatomy (CC BY-SA 4.0), fitted to MS-Human-700'}
    (DATA / 'anatomy.bin').write_bytes(bytes(blob))
    (DATA / 'anatomy.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print('bodies', len(skin_bodies), 'objects', len(objects), 'MB', round(len(blob) / 1e6, 1))
    worst = sorted(report.items(), key=lambda kv: -kv[1]['median_gap_mm'])[:8]
    print('largest fit gaps', worst)
    mapped = sorted({o['base'] for o in objects if o['kind'] == 'muscle' and o['drivers']})
    print('muscles driven by the simulation:', len(mapped), mapped)


if __name__ == '__main__':
    main()
