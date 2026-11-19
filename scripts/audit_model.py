"""Inspect downloaded XML and numeric motion data, then attempt MuJoCo compilation."""

import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / 'vendor' / 'MS-Human-700'
MOTION = ROOT / 'vendor' / 'msgym' / 'msgym' / 'motion_data' / 'walking_gait.npz'
OUTPUT = ROOT / 'results' / 'model_audit'


def expand_xml(path, active=()):
    path = path.resolve()
    if not path.is_relative_to(MODELS.resolve()) or path in active:
        raise ValueError(f'Invalid or cyclic include: {path}')
    root = ET.parse(path).getroot()
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag == 'include':
                # MuJoCo resolves included files against the top-level model directory.
                included = expand_xml(MODELS / child.attrib['file'], (*active, path))
                index = list(parent).index(child)
                parent.remove(child)
                for offset, item in enumerate(list(included)):
                    parent.insert(index + offset, item)
    return root


def inspect_xml(filename):
    tree = expand_xml(MODELS / filename)
    joints = list(tree.findall('.//worldbody//joint'))
    if tree.findall('.//worldbody//freejoint') or any(
        joint.get('type', 'hinge') not in ('hinge', 'slide') for joint in joints
    ):
        raise ValueError('Scalar joint coordinate assumption must be revised')
    actuators = list(tree.findall('./actuator/*'))
    return {
        'filename': filename,
        'source_sha256': hashlib.sha256((MODELS / filename).read_bytes()).hexdigest(),
        'xml_joint_count': len(joints),
        'xml_body_count_excluding_world': len(tree.findall('.//worldbody//body')),
        'xml_actuator_count': len(actuators),
        'joint_names': [joint.get('name') for joint in joints],
        'actuator_names': [actuator.get('name') for actuator in actuators],
        'joint_equalities': [dict(item.attrib) for item in tree.findall('./equality/joint')],
        'keyframe_coordinate_count': len(tree.find('./keyframe/key').get('qpos').split()),
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {'stage': 'source and numeric data audit', 'motion': {}, 'models': []}
    with np.load(MOTION, allow_pickle=False) as motion:
        report['motion']['file'] = str(MOTION.relative_to(ROOT))
        report['motion']['sha256'] = hashlib.sha256(MOTION.read_bytes()).hexdigest()
        report['motion']['fields'] = {}
        for key in motion.files:
            try:
                values = motion[key]
            except ValueError as error:
                if 'Object arrays cannot be loaded' not in str(error):
                    raise
                report['motion']['fields'][key] = {'loaded': False, 'reason': 'object metadata requires pickle'}
                continue
            if not np.issubdtype(values.dtype, np.number):
                raise ValueError(f'Unexpected nonnumeric field: {key}')
            if not np.isfinite(values).all():
                raise ValueError(f'Nonfinite motion values: {key}')
            record = {'loaded': True, 'shape': list(values.shape), 'dtype': str(values.dtype), 'finite': True}
            if values.ndim == 0:
                record['value'] = values.item()
            report['motion']['fields'][key] = record
        qpos = motion['qpos_traj']
        xpos = motion['xpos_traj']
        rate = float(motion['framerate'])
        if qpos.ndim != 2 or rate <= 0 or qpos.shape[0] < 3:
            raise ValueError('Invalid motion dimensions or rate')
        report['motion']['frame_count'] = len(qpos)
        report['motion']['sample_rate_hz'] = rate
        report['motion']['sample_span_s'] = (len(qpos) - 1) / rate
        report['motion']['repository_cycle_duration_s'] = len(qpos) / rate
        report['motion']['external_loads_present'] = any(
            token in key.lower() for key in motion.files for token in ('grf', 'contact_force', 'wrench', 'torque')
        )
        with (OUTPUT / 'reference_coordinates.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            # Use source indices until correspondence with the compiled model is established.
            writer.writerow(['time_s', *(f'source_qpos_{i}' for i in range(qpos.shape[1]))])
            for index, row in enumerate(qpos):
                writer.writerow([index / rate, *row])

    for filename in ('MS-Human-700.xml', 'MS-Human-700-Locomotion.xml'):
        report['models'].append(inspect_xml(filename))
    full, legs = report['models']
    if full['xml_joint_count'] != qpos.shape[1]:
        raise ValueError('Reference and full model coordinate counts differ')
    if xpos.shape != (len(qpos), full['xml_body_count_excluding_world'] + 1, 3):
        raise ValueError('Reference body-position shape and XML body count differ')
    if [model['xml_actuator_count'] for model in report['models']] != [700, 100]:
        raise ValueError('Unexpected actuator counts in pinned model sources')
    if any(model['xml_joint_count'] != model['keyframe_coordinate_count'] for model in report['models']):
        raise ValueError('Keyframe coordinate count mismatch')
    if not set(legs['joint_names']).issubset(full['joint_names']):
        raise ValueError('Leg joint names are not a subset of full model')
    report['coordinate_mapping'] = {
        'source_column_order_validated': False,
        'xml_names_compatible': True,
        'legs_to_full_xml_joint_indices': [full['joint_names'].index(name) for name in legs['joint_names']],
        'note': 'XML names and dimensions match; compiled kinematic correspondence remains pending.',
    }
    report['mujoco'] = {'imported': False, 'compiled': False}
    try:
        import mujoco
    except ImportError as error:
        report['mujoco']['error'] = str(error)
        report['mujoco']['cause'] = str(error.__cause__) if error.__cause__ else None
    else:
        report['mujoco']['imported'] = True
        report['mujoco']['version'] = mujoco.__version__
        for model_record in report['models']:
            model = mujoco.MjModel.from_xml_path(str(MODELS / model_record['filename']))
            data = mujoco.MjData(model)
            mujoco.mj_resetDataKeyframe(model, data, 0)
            mujoco.mj_forward(model, data)
            if not np.isfinite(data.qacc).all():
                raise ValueError('Nonfinite initialization accelerations')
            model_record['compiled'] = {'nq': model.nq, 'nv': model.nv, 'nu': model.nu, 'nbody': model.nbody}
        report['mujoco']['compiled'] = True
    (OUTPUT / 'audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Motion: {len(qpos)} frames, {rate:g} Hz, {qpos.shape[1]} source coordinates')
    for model in report['models']:
        print(f'{model["filename"]}: XML joints={model["xml_joint_count"]}, actuators={model["xml_actuator_count"]}')
    print(f'MuJoCo compiled: {report["mujoco"]["compiled"]}')
    if 'error' in report['mujoco']:
        print('MuJoCo import blocker:', report['mujoco'])


if __name__ == '__main__':
    main()
