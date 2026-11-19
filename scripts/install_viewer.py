"""Install the official portable Windows viewer in the project directory."""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.17.0'
URL = f'https://github.com/google-deepmind/mujoco/releases/download/{VERSION}/mujoco-{VERSION}-windows-x86_64.zip'
SHA256 = '84d92054e767d0b24b7a8a5c7f3e34e883eb8e4bf7e8eefd7604dd09d999a517'


def main():
    destination = ROOT / 'programs' / f'mujoco-{VERSION}'
    destination.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={'User-Agent': 'kas-animasyon-research'})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != SHA256:
        raise ValueError('Official release SHA256 mismatch')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for item in archive.infolist():
            parts = PurePosixPath(item.filename).parts
            if any(part in ('.', '..') or ':' in part or '\\' in part for part in parts):
                raise ValueError('Unsafe archive member')
            path = destination.joinpath(*parts)
            if not path.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Extraction escapes project directory')
            if item.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(item))
    viewers = list(destination.rglob('simulate.exe'))
    compilers = list(destination.rglob('compile.exe'))
    if len(viewers) != 1:
        raise ValueError(f'Expected one simulate.exe, found {len(viewers)}')
    manifest = {'version': VERSION, 'source': URL, 'sha256': actual,
                'viewer': str(viewers[0]),
                'compiler': str(compilers[0]) if len(compilers) == 1 else None}
    (destination / 'installation.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
