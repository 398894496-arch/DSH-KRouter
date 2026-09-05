#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
FORCE=0
WITH_HOOKS=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --with-hooks) WITH_HOOKS=1 ;;
    -h|--help)
      printf '%s\n' "usage: install.sh [--force] [--with-hooks]"
      printf '%s\n' "copies the KRouter Obsidian skill to ~/.agents/skills/krouter-obsidian"
      printf '%s\n' "copies a Cursor always-on rule to ~/.cursor/rules/"
      printf '%s\n' "copies the ask-as-product rule to ~/.cursor/rules/ask-product.mdc"
      printf '%s\n' "self-evolution timer is on by default"
      printf '%s\n' "DSH-KRouter writer: detect a logged-in Claudian-class CLI, or wire *_API_KEY"
      printf '%s\n' "does not overwrite an existing skill unless --force"
      printf '%s\n' "does not enable hooks unless --with-hooks"
      exit 0
      ;;
  esac
done

SKILL_SRC="$ROOT/skill/krouter-obsidian"
SKILL_DST="${KROUTER_SKILL_HOME:-$HOME/.agents/skills/krouter-obsidian}"
RULE_DST="${KROUTER_CURSOR_RULE:-$HOME/.cursor/rules/krouter-obsidian.mdc}"
ASK_RULE_DST="${KROUTER_ASK_RULE:-$HOME/.cursor/rules/ask-product.mdc}"

if [ -e "$SKILL_DST" ] && [ "$FORCE" -ne 1 ]; then
  printf '%s\n' "skill already exists: $SKILL_DST"
  printf '%s\n' "pass --force to replace. Refusing so a live map is not overwritten by the 8-topic template."
  exit 1
fi

mkdir -p "$(dirname "$SKILL_DST")" "$(dirname "$RULE_DST")" "$(dirname "$ASK_RULE_DST")"
rm -rf "$SKILL_DST"
cp -R "$SKILL_SRC" "$SKILL_DST"
chmod +x "$SKILL_DST/scripts/route_knowledge.sh" "$SKILL_DST/scripts/route_knowledge.py" \
  "$SKILL_DST/scripts/canonical_lookup.py" "$SKILL_DST/scripts/ask_product.py"
cp "$ROOT/extras/cursor/krouter-obsidian.mdc" "$RULE_DST"
cp "$ROOT/extras/cursor/ask-product.mdc" "$ASK_RULE_DST"

printf '%s\n' "skill: $SKILL_DST"
printf '%s\n' "cursor rule: $RULE_DST"
printf '%s\n' "ask rule: $ASK_RULE_DST"
printf '%s\n' "Codex snippet: $ROOT/extras/codex/AGENTS.snippet.md"
printf '%s\n' "Claude Code snippet: $ROOT/extras/claude-code/CLAUDE.snippet.md"

RUN_SH="$ROOT/extras/host-daily-evolution/run.sh"
chmod +x "$RUN_SH" "$ROOT/extras/host-daily-evolution/check.sh" \
  "$ROOT/extras/host-daily-evolution/resolve.py" "$ROOT/extras/host-daily-evolution/wire_keys.py"
WRITER="${KROUTER_WRITER:-}"
KEYS_ENV="${KROUTER_KEYS_ENV:-$HOME/.dsh-krouter-keys.env}"
if [ -z "$WRITER" ]; then
  WRITER=$(python3 "$ROOT/extras/host-daily-evolution/wire_keys.py" --detect) || WRITER=""
  if [ -n "$WRITER" ]; then
    export KROUTER_WRITER=$WRITER
    printf '%s\n' "detected writer: $WRITER"
  fi
fi
printf '%s\n' "self-evolution writer: $RUN_SH"
printf '%s\n' "keys file: $KEYS_ENV (chmod 600). never written into the vault."
wire=$(python3 "$ROOT/extras/host-daily-evolution/wire_keys.py") || wire="missing path=$KEYS_ENV"
printf '%s\n' "key wire: $wire"
case "$wire" in
  present\ *)
    printf '%s\n' "HOST: live graft probed (CLI login or API key). Marker in $KEYS_ENV."
    key_field=present
    ;;
  dead\ *)
    printf '%s\n' "HOST ACTION: existing key failed probe. Replace the API key in $KEYS_ENV, or re-login the CLI."
    key_field=dead
    ;;
  unknown\ *)
    printf '%s\n' "HOST ACTION: could not probe (network). Re-run install.sh when online."
    key_field=missing
    ;;
  *)
    printf '%s\n' "HOST ACTION: self-evolution key missing. Login grok / official Codex / claude, or put *_API_KEY in $KEYS_ENV or on the vault page."
    key_field=missing
    ;;
esac
printf '%s\n' "mounted agent runs status and must tell the host if host_action is present."
if [ -z "${OBSIDIAN_VAULT:-}" ]; then
  printf '%s\n' "timer not loaded: export OBSIDIAN_VAULT to YOUR vault (copy template/ there first), then re-run install.sh."
  printf '%s\n' "do not point the timer at the clone template."
else
  VAULT=$OBSIDIAN_VAULT
  HEALTH="$VAULT/90 系统文件/自动化/日更健康.md"
  if [ -f "$HEALTH" ]; then
    python3 "$ROOT/extras/host-daily-evolution/patch_health.py" "$HEALTH" self_evolution_key "$key_field" || true
    if [ -n "$WRITER" ]; then
      python3 "$ROOT/extras/host-daily-evolution/patch_health.py" "$HEALTH" krouter_writer present || true
    else
      python3 "$ROOT/extras/host-daily-evolution/patch_health.py" "$HEALTH" krouter_writer missing || true
    fi
  fi
  case "$(uname -s)" in
    Darwin)
      DST="$HOME/Library/LaunchAgents/local.dsh-krouter.daily-evolution.plist"
      mkdir -p "$HOME/Library/LaunchAgents"
      ROUTER="$ROOT/skill/krouter-obsidian/scripts/route_knowledge.sh"
      TIMER_PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:$HOME/.grok/bin:$HOME/.local/bin"
      sed -e "s|__RUN_SH__|$RUN_SH|g" -e "s|__VAULT__|$VAULT|g" -e "s|__HOME__|$HOME|g" \
        -e "s|__ROUTER__|$ROUTER|g" -e "s|__PATH__|$TIMER_PATH|g" \
        -e "s|__WRITER__|$WRITER|g" -e "s|__KEYS_ENV__|$KEYS_ENV|g" \
        "$ROOT/extras/host-daily-evolution/launchd.example.plist" > "$DST"
      if [ "${KROUTER_SKIP_LAUNCHD:-}" = "1" ]; then
        printf '%s\n' "self-evolution timer plist written (load skipped): $DST"
      else
        uid=$(id -u)
        launchctl bootout "gui/$uid/local.dsh-krouter.daily-evolution" >/dev/null 2>&1 || true
        if launchctl bootstrap "gui/$uid" "$DST" >/dev/null 2>&1 || launchctl load "$DST" >/dev/null 2>&1; then
          printf '%s\n' "self-evolution timer loaded: $DST vault=$VAULT"
        else
          printf '%s\n' "self-evolution timer plist written: $DST"
        fi
      fi
      ;;
    *)
      printf '%s\n' "install extras/host-daily-evolution/cron.example with OBSIDIAN_VAULT=$VAULT"
      ;;
  esac
  python3 "$ROOT/extras/host-daily-evolution/resolve.py" --sync-health --offline >/dev/null || true
fi
printf '%s\n' "next: run ./scripts/first_run.sh against the template, then point OBSIDIAN_VAULT at your vault."

if [ "$WITH_HOOKS" -eq 1 ]; then
  HOOK_DST="${KROUTER_HOOK_HOME:-$HOME/.cursor/hooks/krouter-exec-gate.py}"
  mkdir -p "$(dirname "$HOOK_DST")"
  cp "$ROOT/extras/hooks/exec-gate.py" "$HOOK_DST"
  printf '%s\n' "hook script: $HOOK_DST"
  printf '%s\n' "merge extras/hooks/hooks.json.example into ~/.cursor/hooks.json and replace the python3 path with:"
  printf '%s\n' "python3 $HOOK_DST"
  printf '%s\n' "hook process must inherit OBSIDIAN_VAULT. default install does not rewrite hooks.json."
fi
