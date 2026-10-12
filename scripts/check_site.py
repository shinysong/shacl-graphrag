"""Check generated internal URLs, required pages, and publication boundaries."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'
BASE = '/shacl-graphrag'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src'} and value:
                self.links.append(value)


def main():
    errors = []
    for page in SITE.rglob('*.html'):
        parser = Links()
        parser.feed(page.read_text())
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            path = unquote(url.path)
            if path.startswith('/'):
                if not (path == BASE or path.startswith(BASE + '/')):
                    errors.append(f'{page.relative_to(SITE)}: outside baseurl: {link}')
                    continue
                target = SITE / path[len(BASE):].lstrip('/')
            else:
                target = page.parent / path
            if target.is_dir():
                target /= 'index.html'
            if not target.is_file():
                errors.append(f'{page.relative_to(SITE)}: missing {link}')
    manifest = json.loads((ROOT / '_workspace/chirpy-manifest.json').read_text())
    for url in manifest.values():
        assert (SITE / url.lstrip('/') / 'index.html').is_file(), url
    for source in (ROOT / 'docs/experiments/records').glob('*.json'):
        assert source.read_bytes() == (SITE / source.relative_to(ROOT / 'docs')).read_bytes()
    forbidden = {'.env', 'MEMORY.md', 'AGENTS.md', '_workspace', 'runs', '.git', 'Gemfile', 'Gemfile.lock'}
    assert not any(forbidden.intersection(p.relative_to(SITE).parts) for p in SITE.rglob('*'))
    assert 'Chirpy' in (SITE / 'index.html').read_text()
    assert not errors, '\n'.join(errors)
    print(f'Checked {len(manifest)} preserved pages, internal assets/links, JSON bytes and private-file exclusions.')


if __name__ == '__main__':
    main()
