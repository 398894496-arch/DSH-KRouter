---
name: krouter-obsidian
description: KRouter Obsidian — route knowledge-dependent tasks to the smallest current evidence set in an Obsidian vault using deterministic local search. Use when a request depends on durable user preferences, prior corrections or superseded claims, long-term project history or results, reusable methods or evidence, or the current vault and automation state. Return evidence in-process; do not spawn a retrieval model or add embeddings.
---

# KRouter Obsidian

Set `OBSIDIAN_VAULT` to the vault root. Run retrieval in the current process. Do not spawn a retrieval agent. Do not add vector storage.

Router script (after install): `$HOME/.agents/skills/krouter-obsidian/scripts/route_knowledge.sh`. On Windows use `python3 route_knowledge.py` (same routes).

## Workflow

1. Run `route_knowledge.sh status`. If the receipt has `host_action:`, tell the host that line (paste `*_API_KEY` on `90 系统文件/自动化/自进化钥匙.md`, or log in `grok` / official Codex / `claude` once). Do not print secrets. Then continue the user's question.
2. Choose one route: `status` for current system state; otherwise `preference`, `correction`, `memory`, `project`, or `search`.
3. Send one contiguous distinguishing noun or short phrase. Do not send the full question. Do not join several words with spaces as if they were AND.
4. Run the router script: `route_knowledge.sh <route> [query]` (Windows: `python3 route_knowledge.py`).
5. If the receipt has `canonical_match: true`, cite `canonical_source` as the source. Do not substitute the preferences note unless that is the mapped source.
6. If the receipt has `host_prompt:`, ask the host that sentence and stop. Do not pick a winner among suggestions.
7. Answer and stop when complete. If the receipt has no `canonical_match: true`, `conflict: no`, and lists `suggestions:`, retry **one** suggested alias. Do not treat a suggestion as a hit until the next receipt says `canonical_match: true`. Then open that source. Report any remaining gap.

## Ask (L3)

At the start of a user utterance that is **starting work**, run:

`python3 $HOME/.agents/skills/krouter-obsidian/scripts/ask_product.py ask --query "<user text>"`

If `trigger.ask` is set, ask `prompt` and wait. At most one. After adopt / reject / defer, run `record --file NAME.md --decision …`. `record` does not write `active`. If adopt, do the work; on success run `promote --file NAME.md`. Only `promote` sets `status: active`. Miss / ambiguous / already-asked: continue. Triggers live on the provisional page (`triggers: a; b`) or the vault sidecar; this clone does not ship someone else’s table.

## Boundaries

- The script is read-only. Semantic vault writes need an explicit assignment.
- Prefer canonical, current, `active` evidence. Use `correction` for `supersedes` conflicts.
- Skip `Clippings/`, backups, and cold mirrors. If the receipt source is `candidate` or `rejected`, read it; do not skip the mapped source.
- Do not restart Obsidian or print secrets. Never echo API keys.
- If `status` prints `host_action:`, tell the host. Do not skip that reminder.
- A complete `status` result needs no second lookup.
