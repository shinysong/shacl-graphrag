#!/usr/bin/env bash
# Create local directories and seed .env from example (does not overwrite existing .env).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/lib/common.sh"

DIRS=(
  "${REPO_ROOT}/data/raw"
  "${REPO_ROOT}/data/processed"
  "${REPO_ROOT}/data/kb"
  "${REPO_ROOT}/results"
  "${REPO_ROOT}/runs"
  "${REPO_ROOT}/logs"
  "${REPO_ROOT}/secrets"
)

for d in "${DIRS[@]}"; do
  ensure_dir "$d"
  log "dir: $d"
done

# Keep empty dirs in git via .gitkeep where useful (data/results are gitignored as wholes).
# secrets/ stays local-only.

ENV_EXAMPLE="${REPO_ROOT}/.env.example"
ENV_FILE="${REPO_ROOT}/.env"

if [[ ! -f "${ENV_EXAMPLE}" ]]; then
  die "Missing ${ENV_EXAMPLE}"
fi

if [[ -f "${ENV_FILE}" ]]; then
  log ".env already exists — leaving untouched"
else
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  log "Created .env from .env.example — fill in OPENROUTER_API_KEY before experiments"
fi

log "Workspace directories ready."
