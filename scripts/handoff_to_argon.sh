#!/usr/bin/env bash
# Bridge script: Hand off baton from Codex CLI (or terminal) to Gemini/Antigravity (Argon) in 1-shot mode.
# This avoids keeping an interactive Argon session open, saving context tokens.
# Usage:
#   ./scripts/handoff_to_argon.sh [optional custom prompt]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODEL="${ARGON_MODEL:-gemini-4-argon-medium}"
DEFAULT_PROMPT="Read _workspace/handoff.md and the latest section of MEMORY.md. Execute the task assigned to Gemini/Antigravity in _workspace/handoff.md, then update _workspace/handoff.md and MEMORY.md and exit."

PROMPT="${1:-$DEFAULT_PROMPT}"

echo "[handoff_to_argon] Running 1-shot Argon ($MODEL) on _workspace/handoff.md..."
exec /home/ubuntu/.local/bin/agy \
  --add-dir "$REPO_ROOT" \
  --disable-slash-commands \
  --dangerously-skip-permissions \
  --model "$MODEL" \
  -p "$PROMPT"
