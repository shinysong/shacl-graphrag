#!/usr/bin/env bash
# One-shot host bootstrap for SHACL GraphRAG experiment environment.
#
# Usage (on Ubuntu/Amazon Linux EC2 after clone):
#   chmod +x scripts/*.sh scripts/lib/*.sh
#   ./scripts/bootstrap.sh
#
# Options:
#   --skip-system   Skip OS package install (no sudo needed for remaining steps)
#   --skip-python   Skip venv / pip install
#   --verify-only   Only run verification

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/lib/common.sh"

SKIP_SYSTEM=0
SKIP_PYTHON=0
VERIFY_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --skip-system) SKIP_SYSTEM=1 ;;
    --skip-python) SKIP_PYTHON=1 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      die "Unknown option: $arg"
      ;;
  esac
done

cd "${REPO_ROOT}"
log "REPO_ROOT=${REPO_ROOT}"

if [[ "${VERIFY_ONLY}" -eq 1 ]]; then
  bash "${SCRIPT_DIR}/04_verify.sh"
  exit $?
fi

if [[ "${SKIP_SYSTEM}" -eq 0 ]]; then
  bash "${SCRIPT_DIR}/01_system_packages.sh"
else
  log "Skipping system packages (--skip-system)"
fi

if [[ "${SKIP_PYTHON}" -eq 0 ]]; then
  bash "${SCRIPT_DIR}/02_python_env.sh"
else
  log "Skipping Python env (--skip-python)"
fi

bash "${SCRIPT_DIR}/03_dirs_and_env.sh"
bash "${SCRIPT_DIR}/04_verify.sh"

log "Bootstrap complete."
log "Next: edit .env (OpenRouter); see docs/setup/agents.md for Codex/Orca; then GraphDB/Neo4j + Terraform later."
