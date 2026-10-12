#!/usr/bin/env bash
# Install base OS packages for the experiment host.
# Target OS: Ubuntu 22.04 / 24.04 only.
# Idempotent: safe to re-run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/lib/common.sh"

OS_ID="$(detect_os)"
log "Detected OS: ${OS_ID}"

if [[ "${OS_ID}" != "ubuntu" && "${OS_ID}" != "debian" ]]; then
  die "This project targets Ubuntu 22.04/24.04. Got '${OS_ID}'. Re-image the host as Ubuntu, or install packages manually."
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y \
  build-essential \
  ca-certificates \
  curl \
  git \
  jq \
  unzip \
  wget \
  python3 \
  openjdk-17-jdk-headless \
  docker.io

# Compose plugin package name differs across Ubuntu releases.
if ! sudo apt-get install -y docker-compose-v2; then
  sudo apt-get install -y docker-compose-plugin || warn "docker compose plugin not installed; install later if needed"
fi

if ! groups "$USER" | grep -qw docker; then
  sudo usermod -aG docker "$USER" || true
  warn "Added ${USER} to docker group. Re-login (or newgrp docker) before using docker without sudo."
fi

# --- uv (Astral) ---
export PATH="${HOME}/.local/bin:${PATH}"
if command -v uv >/dev/null 2>&1; then
  log "uv already present: $(uv --version)"
else
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

require_cmd uv
log "uv: $(uv --version)"

# Persist PATH hint for non-login shells (idempotent snippet).
PROFILE_SNIPPET='export PATH="$HOME/.local/bin:$PATH"'
for rc in "${HOME}/.bashrc" "${HOME}/.profile"; do
  if [[ -f "$rc" ]] && ! grep -Fq '.local/bin' "$rc"; then
    printf '\n# uv / user local binaries\n%s\n' "${PROFILE_SNIPPET}" >>"$rc"
    log "Appended PATH hint to ${rc}"
  fi
done

log "System packages step done (Ubuntu + uv)."
