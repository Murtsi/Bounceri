#!/usr/bin/env bash
# Fails when a commit range changes the repo without updating CHANGELOG.md.
# Usage: scripts/check-changelog.sh [BASE] [HEAD]
# Escape hatch: every commit in the range has "[skip changelog]" in its message.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

HEAD_REF="${2:-HEAD}"
BASE_REF="${1:-}"

if [ -z "$BASE_REF" ] || [ "$BASE_REF" = "0000000000000000000000000000000000000000" ] \
  || ! git cat-file -e "${BASE_REF}^{commit}" 2>/dev/null; then
  BASE_REF="$(git merge-base origin/main "$HEAD_REF" 2>/dev/null || true)"
fi

if [ -z "$BASE_REF" ] || [ "$(git rev-parse "$BASE_REF")" = "$(git rev-parse "$HEAD_REF")" ]; then
  echo "changelog: nothing to compare, skipping"
  exit 0
fi

changed="$(git diff --name-only "$BASE_REF" "$HEAD_REF")"
if [ -z "$changed" ]; then
  echo "changelog: no file changes"
  exit 0
fi

if printf '%s\n' "$changed" | grep -qx 'CHANGELOG.md'; then
  echo "changelog: ok (CHANGELOG.md updated)"
  exit 0
fi

total="$(git rev-list --count --no-merges "$BASE_REF..$HEAD_REF")"
skipped="$(git log --no-merges --format=%B%x00 "$BASE_REF..$HEAD_REF" | tr '\0' '\n' | grep -c '\[skip changelog\]' || true)"
if [ "$total" -gt 0 ] && [ "$skipped" -ge "$total" ]; then
  echo "changelog: skipped by [skip changelog]"
  exit 0
fi

echo "changelog: FAIL — these changes are not recorded in CHANGELOG.md:" >&2
printf '%s\n' "$changed" | sed 's/^/  /' >&2
echo >&2
echo "Add a line under '## [Unreleased]' (see AGENTS.md, section 3)." >&2
exit 1
