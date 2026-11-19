"""Replay the recorded successful walk in the local MuJoCo viewer."""
import argparse
from pathlib import Path
import time

import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validate replay states without a window')
    args = parser.parse_args()
    model = mujoco.MjModel.from_xml_path(str(ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'))
    data = mujoco.MjData(model)
    with np.load(ROOT / 'results/baseline/trajectory.npz', allow_pickle=False) as source:
        times = source['time'].copy()
        poses = source['qpos'].copy()
        velocities = source['qvel'].copy()
        activations = source['activation'].copy()
        controls = source['ctrl'].copy()
    if len(times) < 2 or not all(np.isfinite(a).all() for a in (times, poses, velocities, activations, controls)):
        raise ValueError('Missing or invalid recorded walking states')

    def set_frame(index):
        data.time = times[index]
        data.qpos[:] = poses[index]
        data.qvel[:] = velocities[index]
        data.act[:] = activations[index]
        data.ctrl[:] = controls[index]
        mujoco.mj_forward(model, data)

    if args.check:
        for index in (0, len(times) // 2, len(times) - 1):
            set_frame(index)
            if not np.isfinite(data.xpos).all():
                raise ValueError('Replay produced invalid body positions')
        print(f'Replay validated: {len(times)} states, {times[-1]:.3f} seconds')
        return
    from mujoco import viewer as mj_viewer
    set_frame(0)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    camera.trackbodyid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'pelvis')
    camera.distance = 3.2
    camera.azimuth = 90
    camera.elevation = -15
    duration = times[-1] + (times[1] - times[0])
    with mj_viewer.launch_passive(model, data, key_callback=None) as viewer:
        viewer.cam.type = camera.type
        viewer.cam.trackbodyid = camera.trackbodyid
        viewer.cam.distance = camera.distance
        viewer.cam.azimuth = camera.azimuth
        viewer.cam.elevation = camera.elevation
        start = time.perf_counter()
        while viewer.is_running():
            phase = (time.perf_counter() - start) % duration
            index = min(len(times) - 1, int(np.searchsorted(times, phase, side='right')) - 1)
            with viewer.lock():
                set_frame(max(0, index))
            viewer.sync()
            time.sleep(0.01)


if __name__ == '__main__':
    main()
