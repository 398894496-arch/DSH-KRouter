#!/bin/sh
# Self-evolution writer + nightly upkeep. Timer is on by default.
# Key = vault page *_API_KEY or an already-logged-in local CLI. No extra env file.
set -eu

DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$DIR/../.." && pwd)
RESOLVE="$DIR/resolve.py"
BUNDLED_ROUTER="$ROOT/skill/krouter-obsidian/scripts/route_knowledge.sh"

if [ -z "${OBSIDIAN_VAULT:-}" ]; then
  printf '%s\n' "DSH-KRouter: OBSIDIAN_VAULT is not set. Timer on; distill skipped." >&2
  exit 0
fi

case "${KROUTER_ROUTER:-}" in
  *obsidian-knowledge-router*) KROUTER_ROUTER="" ;;
esac
export KROUTER_ROUTER="${KROUTER_ROUTER:-$BUNDLED_ROUTER}"

rc=0
python3 "$RESOLVE" --exec || rc=$?

# Nightly upkeep after the seal. On by default; KROUTER_NIGHTLY=0 turns it off.
# Each step is independent: one failing does not stop the others, and none changes the seal's exit code.
# Steps that need a model use the same lane as the writer: *_API_KEY first, then a logged-in CLI;
# with neither they print "skipped" and exit 0.
if [ "${KROUTER_NIGHTLY:-1}" != 0 ]; then
  SK=$(dirname "$KROUTER_ROUTER")
  [ -f "$SK/recall_index.py" ] || SK="$ROOT/skill/krouter-obsidian/scripts"
  for step in compile_subconscious reconsolidate consolidate_topics answer_cards checkup; do
    if [ -f "$SK/$step.py" ]; then
      python3 "$SK/$step.py" --vault "$OBSIDIAN_VAULT" >&2 || printf '%s\n' "DSH-KRouter: nightly $step failed (rc=$?); continuing" >&2
    fi
  done
fi

exit "$rc"
