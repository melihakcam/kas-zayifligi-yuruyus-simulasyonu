"""Print the MS-Human-700 locomotion model and its rest pose with the native MuJoCo library.

Uses programs/mujoco-3.17.0/bin/mujoco.dll through ctypes, so it also works where the
Python bindings cannot be loaded.

  python scripts/mujoco_rest_pose.py web/build
Writes rest_model.txt and rest_data.txt (MuJoCo's own text dumps, full precision).
"""
import ctypes
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'web/build')
    out.mkdir(parents=True, exist_ok=True)
    dll = ctypes.CDLL(str(ROOT / 'programs/mujoco-3.17.0/bin/mujoco.dll'))
    dll.mj_loadXML.restype = ctypes.c_void_p
    dll.mj_loadXML.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    dll.mj_makeData.restype = ctypes.c_void_p
    dll.mj_makeData.argtypes = [ctypes.c_void_p]
    dll.mj_forward.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    dll.mj_printFormattedModel.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    dll.mj_printFormattedData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    error = ctypes.create_string_buffer(1000)
    xml = ROOT / 'vendor/MS-Human-700/MS-Human-700-Locomotion.xml'
    model = dll.mj_loadXML(str(xml).encode(), None, error, 1000)
    if not model:
        raise RuntimeError(error.value.decode())
    data = dll.mj_makeData(model)
    dll.mj_forward(model, data)
    dll.mj_printFormattedModel(model, str(out / 'rest_model.txt').encode(), b'%.9g')
    dll.mj_printFormattedData(model, data, str(out / 'rest_data.txt').encode(), b'%.9g')
    print('wrote', out / 'rest_model.txt', out / 'rest_data.txt')


if __name__ == '__main__':
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    main()
