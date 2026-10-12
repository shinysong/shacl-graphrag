"""Pin official YAGO 4.6 schema and tiny distribution without downloading all facts."""
import concurrent.futures
import hashlib
import json
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://yago-knowledge.org/data/yago4.6/'
FILES = {'schema': ('yago-4.6-schema.zip', 19471), 'tiny': ('yago-4.6-tiny.zip', 91188862)}


def main():
    out = ROOT / 'data/yago/4.6'
    out.mkdir(parents=True, exist_ok=True)
    existing = json.loads((out / 'manifest.json').read_text()) if (out / 'manifest.json').exists() else None

    def fetch(item):
        kind, (name, size) = item
        path = out / (kind + '.zip')
        headers = {}
        if not path.exists():
            with urllib.request.urlopen(BASE + name, timeout=90) as response, path.with_suffix('.partial').open('wb') as sink:
                headers = {k: response.headers.get(k) for k in ('Last-Modified', 'ETag', 'Content-Length')}
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    sink.write(chunk)
            path.with_suffix('.partial').rename(path)
        if path.stat().st_size != size:
            raise ValueError(f'Unexpected size: {kind}')
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if existing and checksum != existing['files'][kind]['sha256']:
            raise ValueError(f'Cached hash mismatch: {kind}')
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != 1 or not names[0].endswith('.ttl'):
                raise ValueError('Expected one Turtle member')
            with archive.open(names[0]) as source, (out / (kind + '.ttl')).open('wb') as sink:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    sink.write(chunk)
        result = {'url': BASE + name, 'size': size, 'sha256': checksum, 'headers': headers,
                  'member': names[0], 'turtle_sha256': hashlib.sha256((out / (kind + '.ttl')).read_bytes()).hexdigest()}
        print(json.dumps({'file': kind, **result}), flush=True)
        return kind, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        files = dict(pool.map(fetch, FILES.items()))
    manifest = {'dataset': 'YAGO 4.6 official tiny distribution', 'retrieved_at': datetime.now(UTC).isoformat(),
                'release_index': BASE, 'license': 'CC BY 4.0',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                'attribution': 'YAGO team, Télécom Paris. YAGO 4.6: A Logically Consistent Subset of Wikidata (2026).',
                'files': files}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
