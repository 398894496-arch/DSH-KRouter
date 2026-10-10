#!/bin/sh
set -eu

if [ -z "${OBSIDIAN_VAULT:-}" ]; then
  printf '%s\n' "set OBSIDIAN_VAULT to your vault root" >&2
  exit 2
fi
VAULT=$OBSIDIAN_VAULT
ROUTE=${1:-}
QUERY=${2:-}

# One process instead of four: the Python twin runs lock + recall + receipt in-process.
# KROUTER_SH_ONLY=1 keeps the pure-shell path below.
if [ "${KROUTER_SH_ONLY:-0}" != 1 ] && command -v python3 >/dev/null 2>&1 \
  && [ -f "$(dirname "$0")/route_knowledge.py" ]; then
  exec python3 "$(dirname "$0")/route_knowledge.py" "$@"
fi

CANONICAL="$VAULT/Agent第二大脑.md"
PREFERENCES="$VAULT/02 经验与方法/Agent/用户偏好与工作约束.md"
CORRECTIONS="$VAULT/90 系统文件/Agent记忆/纠错与取代记录.md"
MEMORY="$VAULT/90 系统文件/Agent记忆/可靠记忆索引.md"
PROJECTS="$VAULT/01 项目"
HEALTH="$VAULT/90 系统文件/自动化/日更健康.md"
CANONICAL_MAP="$(dirname "$0")/canonical_sources.psv"

usage() {
  printf '%s\n' "usage: route_knowledge.sh {status|preference|correction|memory|project|search|suggest} [literal query]" >&2
  exit 2
}

frontmatter_value() {
  file=$1
  field=$2
  awk -v field="$field" '
    NR == 1 && $0 == "---" { in_frontmatter=1; next }
    in_frontmatter && $0 == "---" { exit }
    in_frontmatter && index($0, field ":") == 1 {
      sub("^[^:]+:[[:space:]]*", "")
      gsub(/^"|"$/, "")
      print
      exit
    }
  ' "$file"
}

file_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -- "$1" | awk '{ print $1 }'
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
  fi
}

emit_receipt() {
  source=$1
  retrieval_status=$2
  printf 'receipt_version: knowledge-route-v2\n'
  printf 'observed_at: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  printf 'requested_route: %s\n' "$ROUTE"
  printf 'query: %s\n' "$QUERY"
  printf 'retrieval_status: %s\n' "$retrieval_status"
  printf 'source: %s\n' "$source"
  if [ -f "$source" ]; then
    source_status=$(frontmatter_value "$source" status)
    source_verified_at=$(frontmatter_value "$source" verified_at)
    [ -n "$source_status" ] && printf 'source_status: %s\n' "$source_status"
    [ -n "$source_verified_at" ] && printf 'source_verified_at: %s\n' "$source_verified_at"
    printf 'source_sha256: %s\n' "$(file_sha256 "$source")"
  fi
  [ -f "$CANONICAL_MAP" ] && printf 'canonical_map_sha256: %s\n' "$(file_sha256 "$CANONICAL_MAP")"
  subconscious="$VAULT/90 系统文件/自动化/下意识.md"
  if [ -f "$subconscious" ]; then
    printf 'subconscious: %s\n' "$subconscious"
    printf 'subconscious_sha256: %s\n' "$(file_sha256 "$subconscious")"
    printf 'subconscious_rows: %s\n' "$(awk '/^Q[0-9]/{n++} END{print n+0}' "$subconscious")"
  else
    printf 'subconscious: missing\n'
  fi
}

emit_host_action() {
  [ -f "$HEALTH" ] || return 0
  lamp=$(frontmatter_value "$HEALTH" lamp)
  key=$(frontmatter_value "$HEALTH" self_evolution_key)
  writer=$(frontmatter_value "$HEALTH" krouter_writer)
  printf 'health: %s\n' "$HEALTH"
  printf 'lamp: %s\n' "${lamp:-unset}"
  printf 'self_evolution_key: %s\n' "${key:-missing}"
  printf 'krouter_writer: %s\n' "${writer:-missing}"
  if [ "${key:-missing}" != "present" ] || [ "${writer:-missing}" != "present" ]; then
    printf '%s\n' "host_action: Distill needs a callable model. Paste *_API_KEY on 90 系统文件/自动化/自进化钥匙.md (flagship is auto-locked), or log in grok / official Codex / claude (your subscription). Timer already on. Do not print secrets."
  fi
}

frontmatter_fields() {
  awk '
    NR == 1 && $0 == "---" { in_frontmatter=1; next }
    in_frontmatter && $0 == "---" { exit }
    in_frontmatter && /^(snapshot_at|verified_at|routing_correction_recorded_at|runtime_observed_at|task_runtime_permission_status|daily_automation_cron_status|daily_automation_document_sync_status|daily_automation_sync_reproducibility_status|semantic_retrieval_status|semantic_answers|historical_canonical_source_precision|current_canonical_routing_status|canonical_routing_map_status|canonical_routing_baseline_cases|canonical_routing_baseline_aliases|canonical_routing_increment_cases|canonical_routing_increment_aliases|canonical_routing_cases|canonical_routing_aliases|canonical_routing_verified_at|semantic_retrieval_rerun_status|knowledge_route_receipt_status|obsidian_app_version|unresolved_links_status|overall_execution_gate|status|updated):/ { print }
  ' "$CANONICAL"
}

emit_daily_seal() {
  # Seal date lives only on the health page. Do not copy it onto Agent第二大脑.
  [ -f "$HEALTH" ] || { printf 'daily_seal: missing\n'; return 0; }
  sealed=$(awk '
    /^- 最近已封：/ {
      if (match($0, /`[0-9]{4}-[0-9]{2}-[0-9]{2}`/)) {
        print substr($0, RSTART + 1, RLENGTH - 2)
        exit
      }
      print "none"
      exit
    }
  ' "$HEALTH")
  pending=$(awk '
    /^- 待总结/ {
      n = split($0, parts, "`")
      if (n >= 2) print parts[2]
      if (match($0, /[0-9]{4}-[0-9]{2}-[0-9]{2}/)) print substr($0, RSTART, 10)
      exit
    }
  ' "$HEALTH")
  through=$(printf '%s\n' "$pending" | awk 'NR==2{print}')
  pending=$(printf '%s\n' "$pending" | awk 'NR==1{print}')
  printf 'daily_seal_source: %s\n' "$HEALTH"
  printf 'daily_seal: %s\n' "${sealed:-missing}"
  [ -n "$through" ] && printf 'daily_seal_through: %s\n' "$through"
  [ -n "$pending" ] && printf 'daily_seal_pending: %s\n' "$pending"
}

md_search() {
  # $1 max matches per file, $2 literal needle, $3 file or directory
  if command -v rg >/dev/null 2>&1; then
    rg -L -F -n -i -C 1 -m "$1" --glob '*.md' --glob '!Clippings/**' -- "$2" "$3" 2>/dev/null || true
  else
    grep -R -F -n -i -C 1 -m "$1" --include='*.md' --exclude-dir=Clippings -- "$2" "$3" 2>/dev/null || true
  fi
}

recall_search() {
  # $1 scope (absolute). Ranked L1 recall over the vault; empty output means it could not run.
  rel=${1#"$VAULT"}
  rel=${rel#/}
  lines=1
  [ -f "$1" ] && lines=4
  python3 "$(dirname "$0")/recall_index.py" --vault "$VAULT" --query "$QUERY" --scope "$rel" \
    --limit 3 --lines "$lines" 2>/dev/null || true
}

bounded_search() {
  scope=$1
  [ -n "$QUERY" ] || usage
  recalled=$(recall_search "$scope")
  if [ "$scope" != "$VAULT" ] && { [ -z "$recalled" ] || printf '%s\n' "$recalled" | grep -q '^recall: none'; }; then
    wide=$(recall_search "$VAULT")
    if [ -n "$wide" ] && ! printf '%s\n' "$wide" | grep -q '^recall: none'; then
      recalled=$(printf 'scope_widened: vault (the route scope had no page covering this question)\n%s' "$wide")
    fi
  fi
  if [ -n "$recalled" ] && ! printf '%s\n' "$recalled" | grep -q '^recall: none'; then
    emit_receipt "$scope" ranked-recall-complete
    emit_suggestions
    printf 'route: %s\n' "$ROUTE"
    printf 'scope: %s\n' "$scope"
    printf '%s\n' "$recalled"
    printf 'open_page: only the top recall hit, and only if its how does not close the question\n'
    return 0
  fi
  emit_receipt "$scope" bounded-literal-search-complete
  emit_suggestions
  printf 'route: %s\n' "$ROUTE"
  printf 'scope: %s\n' "$scope"
  [ -n "$recalled" ] && printf '%s\n' "$recalled" | grep '^recall' || true
  md_search 4 "$QUERY" "$scope" \
    | awk 'NR <= 24 { print } NR == 25 { print "[truncated after 24 lines]"; exit }' || true
}

emit_suggestions() {
  lookup_py="$(dirname "$0")/canonical_lookup.py"
  [ -f "$CANONICAL_MAP" ] || return 0
  [ -n "$QUERY" ] || return 0
  explain=$(python3 "$lookup_py" --map "$CANONICAL_MAP" --vault "$VAULT" --query "$QUERY" --explain) || true
  if [ -n "$explain" ]; then
    printf '%s\n' "$explain"
  fi
  hits=$(python3 "$lookup_py" --map "$CANONICAL_MAP" --vault "$VAULT" --query "$QUERY" --suggest --limit 5) || true
  [ -n "$hits" ] || return 0
  printf 'canonical_match: false\nsuggestions:\n'
  printf '%s\n' "$hits" | awk -F'|' '{ printf "- %s alias=%s source=%s score=%s\n", $1, $2, $3, $4 }'
}

canonical_lookup() {
  [ -n "$QUERY" ] || return 1
  [ -f "$CANONICAL_MAP" ] || return 1
  lookup_py="$(dirname "$0")/canonical_lookup.py"
  hit=$(python3 "$lookup_py" --map "$CANONICAL_MAP" --vault "$VAULT" --query "$QUERY") || return 1
  canonical_id=${hit%%|*}
  rest=${hit#*|}
  relative_source=${rest%%|*}
  canonical_source="$VAULT/$relative_source"
  [ -f "$canonical_source" ] || {
    printf 'Canonical source missing: %s\n' "$canonical_source" >&2
    return 1
  }
  emit_receipt "$canonical_source" canonical-match
  printf 'route: canonical\ncanonical_id: %s\ncanonical_source: %s\ncanonical_match: true\n' \
    "$canonical_id" "$canonical_source"
  anchor=${rest#*|}
  how=$anchor
  l0="$VAULT/90 系统文件/自动化/下意识.md"
  if [ -f "$l0" ]; then
    row=$(awk -F'|' -v id="$canonical_id" '$1==id { print; exit }' "$l0")
    if [ -n "$row" ]; then
      how=$(printf '%s\n' "$row" | awk -F'|' '{ print $4 }')
      flag=$(printf '%s\n' "$row" | awk -F'|' '{ print $5 }')
      [ "$flag" = "yes" ] && printf 'correction_first: yes\n'
    fi
  fi
  printf 'how: %s\n' "$how"
  printf 'open_page: only if how does not close the question\n'
  return 0
}

[ -d "$VAULT" ] || { printf 'Vault not found: %s\n' "$VAULT" >&2; exit 1; }

case "$ROUTE" in
  preference|correction|memory|project|search)
    canonical_lookup && exit 0
    ;;
esac

case "$ROUTE" in
  status)
    emit_receipt "$CANONICAL" requested-fields-returned
    printf 'route: status\nevidence_scope: selected-frontmatter-fields\nl0: how is on the lock receipt; do not ingest 下意识.md\n'
    frontmatter_fields
    emit_daily_seal
    emit_host_action
    ;;
  preference)
    bounded_search "$PREFERENCES"
    ;;
  correction)
    bounded_search "$CORRECTIONS"
    ;;
  memory)
    bounded_search "$MEMORY"
    ;;
  project)
    bounded_search "$PROJECTS"
    ;;
  search)
    bounded_search "$VAULT"
    ;;
  suggest)
    [ -n "$QUERY" ] || usage
    emit_receipt "$CANONICAL_MAP" alias-suggestions
    emit_suggestions
    ;;
  *)
    usage
    ;;
esac
