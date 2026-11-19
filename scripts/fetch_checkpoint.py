"""Fetch the published legs checkpoint without executing its serialized contents."""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/LNSGroup/msgym/releases/download/Checkpoints/LocomotionLegs.zip'
EXPECTED_SHA256 = '8f442634f9e90cf8cd38de22f74fc0da0b9d842b726cbaf812161533e82313f4'


def main():
    destination = ROOT / 'vendor' / 'checkpoints'
    destination.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=120) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != EXPECTED_SHA256:
        raise ValueError('Checkpoint checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for item in archive.infolist():
            parts = PurePosixPath(item.filename).parts
            if any(part in ('.', '..') or ':' in part or '\\' in part for part in parts):
                raise ValueError('Unsafe archive member')
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Archive member escapes destination')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
        inventory = archive.namelist()
    manifest = {'url': URL, 'sha256': EXPECTED_SHA256, 'files': inventory}
    (destination / 'checkpoint_source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
