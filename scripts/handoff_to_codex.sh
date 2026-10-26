#!/usr/bin/env bash
# Bridge script: Hand off baton from Gemini/Antigravity (or terminal) to Codex CLI (gpt-6-astra).
# Usage:
#   ./scripts/handoff_to_codex.sh [optional custom prompt]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

THREAD_ID="${CODEX_THREAD_ID:-01a12efb-aa6d-71a3-a2ec-58a0f7890fd0}"
MODEL="${CODEX_MODEL:-gpt-6-astra}"
OUT_MSG="$REPO_ROOT/_workspace/codex-last-handoff-message.txt"

DEFAULT_PROMPT="Read _workspace/handoff.md and the latest section of MEMORY.md. Execute the Action Queue assigned to Codex CLI (tasks 1-4: independent methods/implementation review via research_ops.py, metric/line-count consistency audit and fixes across docs/journal/2026-10-22-llm-semantic-intervention-paper.md, docs/experiments/research-plan.md, docs/experiments/records/20261022-unified-rule-lifecycle.md, and scripts/unified_rule_lifecycle.py, humanize-korean verify_gates.py check, and mkdocs/build_site.sh verification) autonomously without asking routine questions, then update _workspace/handoff.md and MEMORY.md."

PROMPT="${1:-$DEFAULT_PROMPT}"

echo "[handoff_to_codex] Running Codex ($MODEL) with full workspace access on _workspace/handoff.md..."
exec /home/ubuntu/.local/bin/codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  -C "$REPO_ROOT" \
  -m "$MODEL" \
  -o "$OUT_MSG" \
  "$PROMPT"
