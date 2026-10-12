#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --locked python scripts/prepare_chirpy.py
export BUNDLE_GEMFILE="$PWD/website/Gemfile"
JEKYLL_ENV=production bundle exec jekyll build --source _workspace/chirpy-source --destination site
uv run --locked python scripts/check_site.py
