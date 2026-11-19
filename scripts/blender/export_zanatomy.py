"""Blender: export Z-Anatomy muscles and bones as simplified triangle meshes.

  blender -b --python scripts/blender/export_zanatomy.py -- vendor/z-anatomy web/build/za_raw

Writes <out>.json (object list) and <out>.bin (float32 world positions, uint32
triangles, uint8 material index per triangle). Coordinates are Z-Anatomy's own
(metres, +x = left, +y = posterior, +z = up).
"""
import json
from pathlib import Path
import sys

import bpy

src, out = sys.argv[sys.argv.index('--') + 1:][:2]
src, out = Path(src), Path(out)
out.parent.mkdir(parents=True, exist_ok=True)

SKIP_PARENTS = ('Bursae', 'Extra-ocular', 'Laryngeal', 'Muscles of auditory', 'Muscles of tongue',
                'Muscles of soft palate', 'Pharyngeal', 'Muscles of perineum', 'Muscles of pelvic floor')
SKIP_BONES = ('tooth', 'incisor', 'canine', 'premolar', 'Stapes', 'Malleus', 'Incus', 'Take a picture',
              'Sinus of', 'cells of ethmoid', 'Arytenoid', 'Corniculate', 'Cricoid', 'Thyroid cartilage',
              'nasal septal', 'alar cartilage', 'Nasal septal')
MUSCLE_RATIO, BONE_RATIO, MIN_FACES = 0.22, 0.25, 300


def load(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def keep_muscle(obj):
    if obj.type != 'MESH' or not obj.name.endswith(('.l', '.r')):
        return False
    parent = obj.parent.name if obj.parent else ''
    if any(p in parent for p in SKIP_PARENTS):
        return False
    if 'Fasciae' in parent:
        return 'Iliotibial' in obj.name or 'lata' in obj.name
    return True


def keep_bone(obj):
    if obj.type != 'MESH':
        return False
    if not (obj.name.endswith(('.l', '.r')) or '.' not in obj.name):
        return False
    return not any(s in obj.name for s in SKIP_BONES)


bpy.ops.wm.read_factory_settings(use_empty=True)
muscles = [o for o in load(src / 'MuscularSystem100.fbx') if keep_muscle(o)]
muscle_names = {o.name for o in muscles}
bones = [o for o in load(src / 'SkeletalSystem100.fbx') if keep_bone(o) and o.name not in muscle_names]

depsgraph = bpy.context.evaluated_depsgraph_get()
blob, rows = bytearray(), []
import array
for kind, objs, ratio in (('muscle', muscles, MUSCLE_RATIO), ('bone', bones, BONE_RATIO)):
    for obj in objs:
        tri = obj.modifiers.new('tri', 'TRIANGULATE')
        if len(obj.data.polygons) > MIN_FACES:
            dec = obj.modifiers.new('dec', 'DECIMATE')
            dec.ratio = ratio
        depsgraph = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(depsgraph)
        mesh = ev.to_mesh()
        mw = obj.matrix_world
        pos = array.array('f')
        for v in mesh.vertices:
            p = mw @ v.co
            pos.extend((p.x, p.y, p.z))
        tris = array.array('I')
        mats = array.array('B')
        for poly in mesh.polygons:
            if len(poly.vertices) != 3:
                continue
            tris.extend(poly.vertices)
            mats.append(min(poly.material_index, 255))
        row = {'name': obj.name, 'kind': kind, 'parent': obj.parent.name if obj.parent else None,
               'materials': [s.material.name if s.material else '' for s in obj.material_slots],
               'vert_count': len(mesh.vertices), 'tri_count': len(mats)}
        row['pos'] = len(blob); blob += pos.tobytes()
        row['tri'] = len(blob); blob += tris.tobytes()
        row['mat'] = len(blob); blob += mats.tobytes()
        pad = (-len(blob)) % 4
        blob += b'\0' * pad
        rows.append(row)
        ev.to_mesh_clear()

out.with_suffix('.bin').write_bytes(bytes(blob))
out.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
print('muscles', len(muscles), 'bones', len(bones),
      'verts', sum(r['vert_count'] for r in rows), 'tris', sum(r['tri_count'] for r in rows))
