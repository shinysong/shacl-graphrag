"""Build an isolated Jekyll source from public docs; keep Markdown as the source."""

import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
OUTPUT = ROOT / '_workspace/chirpy-source'
BASEURL = '/shacl-graphrag'
TABS = {
    'index.md': ('about', 'fas fa-flask', 1),
    'experiments/specification.md': ('protocol', 'fas fa-list-check', 2),
    'experiments/records/index.md': ('runs', 'fas fa-vial', 3),
    'journal/index.md': ('journal', 'fas fa-pen-nib', 4),
    'setup/recording.md': ('setup', 'fas fa-circle-info', 5),
}


def page_url(path):
    """Retain the existing MkDocs directory URLs, including README pages."""
    name = path.relative_to(DOCS).as_posix()
    if name == 'index.md':
        return '/about/'
    if path.stem in {'index', 'README'}:
        return '/' + str(path.parent.relative_to(DOCS)).strip('.') + '/'
    return '/' + str(path.relative_to(DOCS).with_suffix('')) + '/'


def rewrite_links(body, source):
    def replace(match):
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or url.netloc or target.startswith(('#', '/')):
            return match.group(0)
        dest = (source.parent / unquote(url.path)).resolve()
        if not dest.is_relative_to(DOCS) or not dest.exists():
            raise ValueError(f'{source.relative_to(ROOT)}: missing or non-doc link {target}')
        if dest.is_dir():
            dest = next((dest / n for n in ('index.md', 'README.md') if (dest / n).exists()), dest)
        if dest.suffix == '.md':
            target = BASEURL + page_url(dest)
        else:
            target = BASEURL + '/' + dest.relative_to(DOCS).as_posix()
        if url.query:
            target += '?' + url.query
        if url.fragment:
            target += '#' + url.fragment
        return f'[{label}]({target})'

    # Fenced examples are source text, not navigational links.
    sections = re.split(r'(^```.*?^```[^\n]*$)', body, flags=re.M | re.S)
    return ''.join(section if i % 2 else re.sub(r'\[([^\]]*)\]\(([^\s)]+)\)', replace, section)
                   for i, section in enumerate(sections))


def prepare():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(ROOT / 'website', OUTPUT, ignore=shutil.ignore_patterns('Gemfile*', 'README.md', 'LICENSE'))
    (OUTPUT / '_posts').mkdir(exist_ok=True)
    (OUTPUT / '_tabs').mkdir(exist_ok=True)
    manifest = {}
    search = []
    for source in sorted(DOCS.rglob('*.md')):
        relative = source.relative_to(DOCS).as_posix()
        if relative == 'README.md':
            continue
        text = source.read_text(encoding='utf-8')
        title_match = re.match(r'^# (.+)\n', text)
        if not title_match:
            raise ValueError(f'Missing title: {relative}')
        title = title_match.group(1)
        body = rewrite_links(text[title_match.end():].lstrip(), source)
        url = page_url(source)
        metadata = dict(title=title, layout='page', permalink=url, toc=True, render_with_liquid=False)
        metadata['mermaid'] = bool(re.search(r'^```mermaid\s*$', body, re.M))
        dated = re.match(r'(\d{4}-\d{2}-\d{2})-(.+)\.md$', source.name)
        if relative in TABS:
            name, icon, order = TABS[relative]
            dest = OUTPUT / '_tabs' / f'{name}.md'
            metadata.update(title=name.capitalize(), icon=icon, order=order)
        elif dated and source.parent.name in {'journal', 'lessons-learned'}:
            metadata['title'] = re.sub(r'^\d{4}-\d{2}-\d{2}[ —–-]+', '', title)
            paragraphs = [p for p in body.split('\n\n') if len(p) > 40 and not p.startswith(('#', '|', '-', '```', '<', '상태:'))]
            if paragraphs:
                metadata['description'] = paragraphs[0].replace('\n', ' ')
            dest = OUTPUT / '_posts' / source.name
            metadata.update(layout='post', date=dated[1] + ' 12:00:00 +0000',
                            categories=['연구 일지' if source.parent.name == 'journal' else '시행착오'],
                            tags=['shacl', 'research'] if source.parent.name == 'journal' else ['engineering'],
                            pin=source.parent.name == 'journal')
        else:
            dest = OUTPUT / 'pages' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
                        + '---\n\n' + body, encoding='utf-8')
        manifest[relative] = url
        search.append(dict(title=title, url=BASEURL + url, categories='', tags='',
                           date=dated[1] if dated else '', content=re.sub(r'<[^>]*>', '', body)))
    # Explicit public, offline HTML artifact; never copy private workspace files.
    preview = DOCS / 'experiments/preview/index.html'
    preview_dest = OUTPUT / preview.relative_to(DOCS)
    preview_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(preview, preview_dest)
    for source in DOCS.rglob('*.json'):
        dest = OUTPUT / source.relative_to(DOCS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    for name, layout, icon, order in [('categories', 'categories', 'fas fa-stream', 6),
                                      ('archives', 'archives', 'fas fa-archive', 7)]:
        (OUTPUT / '_tabs' / f'{name}.md').write_text('---\n' + yaml.safe_dump(dict(
            title=name.capitalize(), layout=layout, icon=icon, order=order, permalink=f'/{name}/')) + '---\n')
    (OUTPUT / 'tags.html').write_text('---\nlayout: tags\ntitle: Tags\npermalink: /tags/\n---\n')
    search_file = OUTPUT / 'assets/js/data/search.json'
    search_file.parent.mkdir(parents=True, exist_ok=True)
    search_file.write_text('---\nlayout: null\nrender_with_liquid: false\n---\n' + json.dumps(search, ensure_ascii=False))
    (ROOT / '_workspace/chirpy-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'Prepared {len(manifest)} pages in {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    prepare()
