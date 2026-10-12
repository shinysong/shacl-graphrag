#!/usr/bin/env bash
# Sanity checks after bootstrap. Non-zero exit if critical tools are missing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/lib/common.sh"

export PATH="${HOME}/.local/bin:${PATH}"

ok=0
fail=0

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf '[OK]   %s\n' "$name"
    ok=$((ok + 1))
  else
    printf '[FAIL] %s\n' "$name"
    fail=$((fail + 1))
  fi
}

check "git" command -v git
check "curl" command -v curl
check "jq" command -v jq
check "python3" command -v python3
check "uv" command -v uv
check "java" command -v java
check "docker" command -v docker
check "pyproject.toml" test -f "${REPO_ROOT}/pyproject.toml"
check ".venv" test -x "${REPO_ROOT}/.venv/bin/python"
check ".env" test -f "${REPO_ROOT}/.env"

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
  check "import:dotenv" "$PY" -c "import dotenv"
  check "import:openai" "$PY" -c "import openai"
  check "import:rdflib" "$PY" -c "import rdflib"
  check "import:pyshacl" "$PY" -c "import pyshacl"
fi

if [[ -f "${REPO_ROOT}/.env" ]]; then
  if grep -q '^OPENROUTER_API_KEY=.\+' "${REPO_ROOT}/.env" \
    && ! grep -q '^OPENROUTER_API_KEY=your_' "${REPO_ROOT}/.env"; then
    printf '[OK]   OPENROUTER_API_KEY set\n'
    ok=$((ok + 1))
  else
    printf '[WARN] OPENROUTER_API_KEY not filled in yet\n'
  fi
fi

printf '\nSummary: %s ok, %s fail\n' "$ok" "$fail"

cat <<'EOF'

Deferred (install later, not part of this bootstrap):
  - GraphDB Free / Neo4j Community
  - Amazon Neptune (Terraform)
  - Terraform stack under infra/terraform/
  - Coding agents: Codex CLI and/or Orca runtime (see docs/setup/agents.md)

EOF

[[ "$fail" -eq 0 ]] || exit 1
log "Verify passed."
