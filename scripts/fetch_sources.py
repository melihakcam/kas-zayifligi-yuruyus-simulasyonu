"""Download pinned public sources and record their provenance inside the project."""

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor'


def request(url):
    headers = {'User-Agent': 'kas-animasyon-research', 'Accept': 'application/vnd.github+json'}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return response.read()


def unpack_repository(repository, revision, destination):
    url = f'https://codeload.github.com/{repository}/zip/{revision}'
    payload = request(url)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member in archive.infolist():
            relative = PurePosixPath(member.filename)
            components = relative.parts[1:]
            if not components:
                continue
            if any(part in ('.', '..') or ':' in part or '\\' in part for part in components):
                raise ValueError(f'Unsafe archive member: {member.filename}')
            target = destination.joinpath(*components)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Archive target escapes destination')
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
    return {'repository': repository, 'revision': revision, 'archive_url': url,
            'archive_sha256': hashlib.sha256(payload).hexdigest(),
            'archive_bytes': len(payload), 'directory': str(destination.relative_to(ROOT))}


def main():
    VENDOR.mkdir(exist_ok=True)
    manifest_path = VENDOR / 'sources.json'
    if manifest_path.exists():
        raise SystemExit('Sources already recorded. Inspect vendor/sources.json before downloading again.')
    commit = json.loads(request('https://api.github.com/repos/LNSGroup/msgym/commits/main'))
    revision = commit['sha']
    tree = json.loads(request(f'https://api.github.com/repos/LNSGroup/msgym/git/trees/{revision}?recursive=1'))
    model = next(item for item in tree['tree'] if item['path'] == 'msgym/MS-Human-700')
    if model['mode'] != '160000':
        raise ValueError('Expected a pinned model submodule')
    records = []
    for repository, version, folder in (
        ('LNSGroup/msgym', revision, 'msgym'),
        ('LNSGroup/MS-Human-700', model['sha'], 'MS-Human-700'),
    ):
        print(f'Downloading {repository} at {version}', flush=True)
        records.append(unpack_repository(repository, version, VENDOR / folder))
    manifest_path.write_text(json.dumps({'sources': records}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'sources': records}, indent=2))


if __name__ == '__main__':
    main()
