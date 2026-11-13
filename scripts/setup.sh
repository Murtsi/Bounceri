#!/usr/bin/env bash
# One-time local bootstrap. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "created .env from .env.example"
else
  echo ".env already exists, leaving it alone"
fi

if [ ! -d .git ]; then
  git init -q
  echo "initialized git repository"
fi

echo
echo "Next:"
echo "  make hooks   # install the pre-commit hook"
echo "  make up      # start Postgres + Adminer"
echo "  make dev     # start your app (configure DEV_CMD first)"
