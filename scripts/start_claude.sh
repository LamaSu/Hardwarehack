#!/usr/bin/env bash
# Build the container (first run only) and start Claude Code inside it.
# Run from Git Bash in the repo root:  ./scripts/start_claude.sh
# Pass "bash" to get a shell instead:  ./scripts/start_claude.sh bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Git Bash needs winpty for interactive Docker sessions.
prefix=()
if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
    prefix=(winpty)
fi

if ! docker image inspect hardwarehack-claude >/dev/null 2>&1; then
    echo "Building the Claude Code image (first run only)..."
    docker compose build
fi

# Copy the host git identity into the container once.
name="$(git config user.name || true)"
email="$(git config user.email || true)"
if [[ -n "$name" && -n "$email" ]]; then
    docker compose run --rm -T claude bash -c \
        "git config --global user.name '$name' && git config --global user.email '$email'"
fi

command="${1:-claude}"
"${prefix[@]}" docker compose run --rm claude "$command"
