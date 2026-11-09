#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --locked python scripts/prepare_chirpy.py
if command -v bundle >/dev/null 2>&1; then
  export BUNDLE_GEMFILE="$PWD/website/Gemfile"
  JEKYLL_ENV=production bundle exec jekyll build --source _workspace/chirpy-source --destination site
else
  sudo docker run --rm -u "$(id -u):$(id -g)" \
    -e BUNDLE_PATH=/gems \
    -e BUNDLE_GEMFILE=/srv/repo/website/Gemfile \
    -e JEKYLL_ENV=production \
    -v "$PWD":/srv/repo \
    -v "$PWD/_workspace/gems":/gems \
    -w /srv/repo ruby:3.4-bookworm \
    bundle exec jekyll build --source _workspace/chirpy-source --destination site
fi
uv run --locked python scripts/check_site.py
