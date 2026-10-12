"""Download one pinned GLEIF Golden Copy CSV release, retaining hashes and metadata."""
import argparse
import concurrent.futures
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://goldencopy.gleif.org/api/v2/golden-copies/publishes'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, help='Previously saved publishes JSON')
    parser.add_argument('--publish-date', help='Exact metadata publish_date; defaults to latest')
    args = parser.parse_args()
    raw = args.metadata.read_bytes() if args.metadata else urllib.request.urlopen(ENDPOINT, timeout=60).read()
    releases = json.loads(raw)['data']
    release = next(r for r in releases if r['publish_date'] == args.publish_date) if args.publish_date else releases[0]
    stamp = release['publish_date'].replace('-', '').replace(':', '').replace(' ', 'T')
    out = ROOT / 'data/gleif' / stamp
    out.mkdir(parents=True, exist_ok=True)
    (out / 'publishes.json').write_bytes(raw)
    cached_manifest = json.loads((out / 'manifest.json').read_text()) if (out / 'manifest.json').exists() else None
    specs = {kind: release[kind]['full_file']['csv'] for kind in ('lei2', 'rr', 'repex')}
    if any(release[k]['publish_date'] != release['publish_date'] for k in specs):
        raise ValueError('Mixed release dates')

    def fetch(item):
        kind, spec = item
        path = out / f'{kind}.csv.zip'
        if not path.exists():
            partial = path.with_suffix('.partial')
            with urllib.request.urlopen(spec['url'], timeout=90) as response, partial.open('wb') as f:
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    f.write(block)
            if partial.stat().st_size != spec['size']:
                raise ValueError(f'Size mismatch: {kind}')
            partial.rename(path)
        if path.stat().st_size != spec['size']:
            raise ValueError(f'Cached size mismatch: {kind}')
        checksum = digest(path)
        if cached_manifest and checksum != cached_manifest['files'][kind]['sha256']:
            raise ValueError(f'Cached checksum mismatch: {kind}')
        entry = {**spec, 'path': str(path.relative_to(ROOT)), 'sha256': checksum}
        print(json.dumps({'downloaded': kind, 'bytes': path.stat().st_size, 'sha256': entry['sha256']}), flush=True)
        return kind, entry

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        files = dict(pool.map(fetch, specs.items()))
    manifest = {'publish_date': release['publish_date'], 'retrieved_at': datetime.now(UTC).isoformat(),
                'metadata_url': ENDPOINT, 'license': 'CC0',
                'license_url': 'https://www.gleif.org/en/meta/lei-data-terms-of-use/', 'files': files}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(str(out / 'manifest.json'))


if __name__ == '__main__':
    main()
