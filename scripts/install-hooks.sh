#!/usr/bin/env bash
# Installs the tracked git hook into .git/hooks. Idempotent.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$(git -C "$ROOT" rev-parse --git-path hooks)"

mkdir -p "$HOOKS"
cp "$ROOT/scripts/hooks/pre-commit" "$HOOKS/pre-commit"
chmod +x "$HOOKS/pre-commit" 2>/dev/null || true
echo "installed pre-commit hook -> $HOOKS/pre-commit"
