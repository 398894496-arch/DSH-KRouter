#!/bin/sh
# Run clone checks on git HEAD only. Uncommitted and untracked files are absent.
# Dirty-worktree pytest is not this test. Fail this script → do not upload.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf '%s\n' "not a git repo" >&2
  exit 1
fi

SHA=$(git rev-parse HEAD)
printf '%s\n' "clean tree = git archive $SHA"
if ! git diff --quiet || ! git diff --cached --quiet; then
  printf '%s\n' "note: worktree is dirty; those files are NOT in this run" >&2
fi
untracked=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')
if [ "$untracked" != 0 ]; then
  printf '%s\n' "note: $untracked untracked path(s) are NOT in this run" >&2
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git archive "$SHA" | tar -x -C "$TMP"
cd "$TMP"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "python3 required" >&2
  exit 1
fi
if ! command -v rg >/dev/null 2>&1; then
  printf '%s\n' "ripgrep (rg) required" >&2
  exit 1
fi

python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python3 -m pip install -q -r requirements.txt -r requirements-dev.txt

python3 -m pytest -q
./scripts/first_run.sh
python3 scripts/verify_canonical_map.py
python3 scripts/verify_sealed_days.py --vault template

printf '%s\n' "clean verify PASS $SHA"
