#!/usr/bin/env bash
# Create project virtualenv with uv and sync dependencies from pyproject.toml.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/lib/common.sh"

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v uv >/dev/null 2>&1; then
  die "uv not found. Run scripts/01_system_packages.sh first, or: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

cd "${REPO_ROOT}"

if [[ ! -f "${REPO_ROOT}/pyproject.toml" ]]; then
  die "Missing ${REPO_ROOT}/pyproject.toml"
fi

log "uv sync (creates .venv, installs deps, writes uv.lock if needed)"
uv sync

log "Python env ready."
log "  Activate:  source ${REPO_ROOT}/.venv/bin/activate"
log "  Or run:    uv run <command>"
