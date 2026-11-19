"""Blender: list objects of the Z-Anatomy FBX files (name, vertex count, bounds).

  blender -b --python scripts/blender/inspect_zanatomy.py -- vendor/z-anatomy/MuscularSystem100.fbx out.json
"""
import json
import sys

import bpy
from mathutils import Vector

path, out = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
rows = []
for obj in bpy.data.objects:
    row = {'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None}
    if obj.type == 'MESH':
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        row['verts'] = len(obj.data.vertices)
        row['min'] = [round(min(c[i] for c in corners), 4) for i in range(3)]
        row['max'] = [round(max(c[i] for c in corners), 4) for i in range(3)]
    rows.append(row)
with open(out, 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=0)
print('objects', len(rows))
