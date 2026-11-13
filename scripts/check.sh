#!/usr/bin/env bash
# Stack-agnostic repository hygiene. Used by CI, the pre-commit hook and `make check`.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

PY=""
for candidate in python3 python; do
  if "$candidate" -c 'import sys' >/dev/null 2>&1; then PY="$candidate"; break; fi
done

status=0
fail() { printf '  FAIL  %s\n' "$1"; status=1; }
pass() { printf '  ok    %s\n' "$1"; }

echo "== repository checks =="

# --- merge conflict markers ---
conflicts="$(git ls-files | grep -v '^scripts/check.sh$' | xargs -r grep -nIE '^(<<<<<<< |=======$|>>>>>>> )' 2>/dev/null || true)"
if [ -n "$conflicts" ]; then
  fail "merge conflict markers"
  printf '%s\n' "$conflicts" | head -20
else
  pass "no conflict markers"
fi

# --- trailing whitespace (markdown needs it for hard line breaks) ---
ws="$(git ls-files | grep -vE '\.(md|snap|svg|lock)$' | xargs -r grep -nIE '[ ]+$' 2>/dev/null || true)"
if [ -n "$ws" ]; then
  fail "trailing whitespace"
  printf '%s\n' "$ws" | head -20
else
  pass "no trailing whitespace"
fi

# --- .env must never be tracked ---
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  fail ".env is tracked by git"
else
  pass ".env is not tracked"
fi

# --- JSON parses ---
json_bad=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  "$PY" -c 'import json,sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$f" >/dev/null 2>&1 \
    || { fail "invalid JSON: $f"; json_bad=1; }
done < <(git ls-files '*.json')
[ "$json_bad" -eq 0 ] && pass "all JSON files parse"

# --- YAML parses (skipped when PyYAML is missing) ---
if "$PY" -c 'import yaml' >/dev/null 2>&1; then
  yaml_bad=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    "$PY" -c 'import sys,yaml; yaml.safe_load(open(sys.argv[1], encoding="utf-8"))' "$f" >/dev/null 2>&1 \
      || { fail "invalid YAML: $f"; yaml_bad=1; }
  done < <(git ls-files '*.yml' '*.yaml')
  [ "$yaml_bad" -eq 0 ] && pass "all YAML files parse"
else
  echo "  skip  YAML validation (no Python/PyYAML)"
fi

# --- obvious secrets ---
secret_hits="$(git ls-files | grep -vE '^(\.env\.example|docs/|scripts/)' | xargs -r grep -nIE '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)' 2>/dev/null || true)"
if [ -n "$secret_hits" ]; then
  fail "possible committed secret"
  printf '%s\n' "$secret_hits" | head -10
else
  pass "no obvious secrets"
fi

# --- shellcheck when available ---
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck scripts/*.sh scripts/hooks/* >/dev/null 2>&1; then
    pass "shellcheck"
  else
    fail "shellcheck"
    shellcheck scripts/*.sh scripts/hooks/* || true
  fi
else
  echo "  skip  shellcheck (not installed)"
fi

echo
if [ "$status" -eq 0 ]; then
  echo "all checks passed"
else
  echo "checks failed"
fi
exit "$status"
