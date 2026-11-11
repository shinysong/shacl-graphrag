"""Publish explicitly queued public articles from an isolated checkout.

The local queue is ignored by Git. No queue means no commit or push.
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '_workspace/publication'
QUEUE = STATE / 'ready.json'
BRANCH = 'cursor/add-readme-gitignore'
REPOSITORY = 'git@github.com:shinysong/shacl-graphrag.git'
POST = re.compile(r'docs/journal/(\d{4}-\d{2}-\d{2})-[a-z0-9-]+\.md\Z')
ASSET = re.compile(r'docs/assets/images/[a-zA-Z0-9_./-]+\.(?:png|svg)\Z')


def eligible_paths(raw, root=ROOT, today=None):
    """Accept only dated journal posts and their public image assets."""
    today = today or date.today()
    if not isinstance(raw, list) or not raw or any(not isinstance(p, str) for p in raw):
        raise ValueError('ready.json must contain a nonempty paths list')
    if len(set(raw)) != len(raw):
        raise ValueError('duplicate publication path')
    posts = []
    for relative in raw:
        match = POST.fullmatch(relative)
        if match:
            if date.fromisoformat(match.group(1)) > today:
                raise ValueError(f'future-dated post: {relative}')
            posts.append(relative)
        elif not ASSET.fullmatch(relative) or '..' in Path(relative).parts:
            raise ValueError(f'path is outside the article allowlist: {relative}')
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'missing or linked publication file: {relative}')
        if match and not path.read_text(encoding='utf-8').startswith('# '):
            raise ValueError(f'post lacks an H1 heading: {relative}')
    if not posts:
        raise ValueError('at least one dated journal post is required')
    return raw


def run(*args, cwd=ROOT, env=None):
    subprocess.run(args, cwd=cwd, env=env, check=True)


def receipt(attempt, status, paths, **details):
    payload = dict(attempt=attempt, status=status, paths=paths,
                   recorded_at=datetime.now(timezone.utc).isoformat(), **details)
    destination = STATE / 'attempts' / f'{attempt}.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='commit and push ready articles')
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'publication.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not QUEUE.exists():
            print('No ready articles; no push.')
            return
        queued_bytes = QUEUE.read_bytes()
        paths = eligible_paths(json.loads(queued_bytes)['paths'])
        if not args.publish:
            print(json.dumps(dict(ready=paths, action='dry_run'), ensure_ascii=False))
            return

        attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        checkout = STATE / f'checkout-{attempt}'
        stage = 'fetch'
        worktree_created = False
        try:
            remote = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, text=True).strip()
            if remote != REPOSITORY:
                raise ValueError(f'unexpected origin: {remote}')
            run('git', 'fetch', '--quiet', 'origin', BRANCH)
            base = subprocess.check_output(['git', 'rev-parse', f'origin/{BRANCH}'], cwd=ROOT, text=True).strip()
            stage = 'worktree'
            run('git', 'worktree', 'add', '--detach', '--quiet', str(checkout), base)
            worktree_created = True
            for relative in paths:
                target = checkout / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            run('git', 'add', '--', *paths, cwd=checkout)
            changed = subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=checkout).returncode
            if changed == 0:
                status = 'already_published'
                commit = base
            elif changed == 1:
                stage = 'validate'
                run('git', 'diff', '--cached', '--check', cwd=checkout)
                run('uv', 'run', '--locked', '--group', 'docs', 'mkdocs', 'build', '--strict', cwd=checkout)
                env = os.environ.copy()
                env['CHIRPY_GEMS_PATH'] = str(ROOT / '_workspace/gems')
                run('./scripts/build_site.sh', cwd=checkout, env=env)
                stage = 'commit'
                run('git', '-c', 'user.name=Research Site Publisher',
                    '-c', 'user.email=research-site-publisher@users.noreply.github.com',
                    'commit', '-m', f'Publish ready research articles {date.today().isoformat()}', cwd=checkout)
                commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip()
                stage = 'push'
                run('git', 'push', 'origin', f'HEAD:refs/heads/{BRANCH}', cwd=checkout)
                status = 'pushed'
            else:
                raise RuntimeError(f'git diff failed with exit code {changed}')
            receipt(attempt, status, paths, commit=commit, base=base)
            if QUEUE.exists() and QUEUE.read_bytes() == queued_bytes:
                QUEUE.unlink()
            print(f'{status}: {commit}')
        except Exception as error:
            receipt(attempt, 'failed', paths, stage=stage, error=str(error))
            raise
        finally:
            if worktree_created:
                run('git', 'worktree', 'remove', '--force', str(checkout))


if __name__ == '__main__':
    main()
