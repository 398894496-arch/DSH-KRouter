# Changelog

## 0.7.0 — 2026-10-10

Memory maintenance, measured on the router's own real traffic. 92 de-duplicated queries the author's agents actually sent in 30 days, blind-judged (old vs new shuffled, Opus scores 0/1/2): mean 0.68 → 1.18, direct hits 18 → 38, useless 47 → 21. Synthetic held-out set unchanged (right page 88%, top-1 75%, wrong locks 0, 0/6 off-topic answered); p50 ~115 ms.

- **Lock**: the whitespace token fallback only counts whole-alias hits, so `纠错` no longer locks `纠错优先级` for `Claude Code 纠错`. A source page whose `status` is superseded / retired / rejected / deprecated / archived is out of force: no lock, no L0 row.
- **Recall**: a one-keyword query (`DSH`, `SyGJ`) answers when its one content term matches; bare numbers are not content terms. Trigger text now feeds the word-likeness statistics.
- **Scope widening**: `preference` / `correction` / `memory` / `project` widen to the whole vault (rule pages first) when their own scope has no page that covers the question, and print `scope_widened: vault`.
- **Query log**: one JSONL line per routed query under `~/.local/state/krouter/` (`KROUTER_NO_QUERY_LOG=1` turns it off). Half of real calls repeat an earlier question.
- **`reconsolidate.py`** (nightly, one model call): weak queries + their recall candidates → the model picks the page that answers, or none → `rel|original query` appended to `90 系统文件/**/下意识触发词-自学习.psv`. Recall-only, never a lock, no invented paraphrase. Replay on history: 8 learned, 20 none, 12/12 off-topic probes refused.
- **`checkup.py`** (nightly, no model): writes `90 系统文件/自动化/下意识体检.md` — locks and triggers pointing at missing / dead pages, `supersedes` pairs where recall still ranks the replaced page first, rule pages nobody read or recalled in 60 days. Lists only; never edits sources.

## 0.6.0 — 2026-10-10

A lock miss is now answered by **L1 recall** instead of a whole-sentence literal grep. `skill/krouter-obsidian/scripts/recall_index.py` keeps a rebuildable SQLite FTS5 cache under `~/.cache/krouter/` (stdlib only, no service, no vectors): CJK bigrams + latin words, title and triggers weighted, rule pages first, `superseded` pages sink, cross-word junk bigrams filtered. Each hit prints its `how` line and the best matching line; weak overlap prints `recall: none` and must not guess. Triggers come from the alias table plus any `90 系统文件/**/下意识触发词.psv` (`rel|phrase;phrase`) and never lock.

The lock got stricter: a short alias inside a longer question (`日更` in `日更能不能交给云端跑`) only ranks suggestions. `route_knowledge.sh` now execs the Python twin (one process instead of four); `KROUTER_SH_ONLY=1` keeps the shell path. Ships the L0 compiler `compile_subconscious.py` and the `status` seal lines (`daily_seal*`) from the health page.

Field self-report, author vault (not in clone): 30 held-out questions written before tuning, right page 21% → 88%, top-1 0% → 75%, wrong locks 0, 0/6 off-topic answered, p50 118 ms. Clone tests: `tests/test_recall_index.py`.

## 0.5.1 — 2026-09-05

Windows can run the same lock through `skill/krouter-obsidian/scripts/route_knowledge.py`; DSH on win32 prefers that file. Same-score miss across two pages prints `host_prompt` and must not guess. `sha256` falls back to Python when `shasum` is missing. One protocol, two launchers. Does not ship L0 / `下意识.md`.

## 0.5.0 — 2026-08-31

Ask-as-product matcher in `skill/krouter-obsidian/scripts/ask_product.py`. At most one provisional page per utterance. `record` never writes `active`; `promote` does, after adopt + this task accepted. Triggers live on the page (`triggers:`) or `90 系统文件/自动化/ask-triggers.json`. `install.sh` copies `extras/cursor/ask-product.mdc`. This clone does not ship an author’s trigger table. Codex / Claude still paste the snippet.

## 0.4.3 — 2026-08-28

Lock-vs-neighbor Claim C: multilingual MiniLM; CJK inversion gone; `H15` 发版 already ranks the seal page before any floor (precision, not a threshold miss). Claim D: BGE-M3 middleweight dense; hit 16/16; at 0.40 the leftover is neighbor `B03` (生产事故 → timer), not one of the 12 OOD negatives. Do not merge C and D into “neither matched the lock.” On this contract (refuse + no neighbor cite), featherweight beats that middleweight stack — the “better than mainstream embedding RAG” line. Heavyweight hybrid + rerank is out of scope. Pytest replays frozen JSON (no extra pip in CI). Hub snapshots are not in the clone. Ship `scripts/verify_clean.sh` so the upload gate named in CONTRIBUTING exists in the clone.

## 0.4.2 — 2026-08-27

Ship `in_force` / `live_rows` / `parse_frontmatter` on `canonical_lookup.py`. `verify_canonical_map.py` and the lock-vs-neighbor runner imported them since 0.4.1; the lookup module on GitHub did not. Clone `python3 scripts/verify_canonical_map.py` raised `ImportError`. Not L0.

## 0.4.1 — 2026-08-27

Docs and checkers. No new product lane.

- Evidence is three layers in `docs/VERIFY.md` and the README: implementation (`clone_25`), comparison (`lock_vs_neighbor`), field self-report (author vault, not in clone). `clone_25` 25/25 is not the LLM 25/25.
- Sealed-day gap checker: `scripts/verify_sealed_days.py`. Same trust model as `verify_canonical_map.py` — measures this vault’s `05 时间日志/`, does not replay the author’s 72 consecutive seals. Empty files and `待总结` / `to-summarize` are gaps; a real note on the same day beats a stub.

Already on `main` since 0.4.0, first tagged here: public lock-vs-neighbor fixture (N=36), `clone_25` analogue, host-facing listing, both rungs of the ladder, receipt SVGs, latin-fragment alias rule, API-key-first / CLI subscription writer.

## 0.4.0 — 2026-08-21

- Memory-system tools on the DSH mount: `preference`, `correction`, `memory`, `project` in addition to `status` / `search` / `suggest`.
- Claude Code mount: `extras/claude-code/CLAUDE.snippet.md`.
- Self-evolution extra is now files plus `check.sh`. Template lamp defaults to `unused`. `first_run.sh` proves the extra without starting a timer.
- README maps each listing word to a path in this repo.

## 0.3.1 — 2026-08-21

- Public listing: **DSH-KRouter**. Keyword subtitle: DeepSeek Harness memory system, Agent second brain, Obsidian knowledge base, optional self-evolution, Cursor / Codex / Claude Code.
- Daily evolution extra documents the host scheduler contract. `dsh plugin add` still does not create a cron.

## 0.3.0 — 2026-08-21

- DSH mount: `extras/dsh` registers read-only `krouter_status`, `krouter_search`, `krouter_suggest`.
- Bridge tests on the template vault. No write routes. Uninstall does not delete the vault.
- Same `OBSIDIAN_VAULT` and alias map as Cursor and Codex.

## 0.2.0 — 2026-08-21

- CI: pytest + `first_run.sh` on every push to `main`.
- `suggest` route: prefix/overlap alias hints on a miss. Hints are not hits.
- Miss receipts include `suggestions:` so an agent can retry one noun.
- Public unit tests for exact match, same-file ties, and ambiguous miss.

## 0.1.0 — 2026-08-21

- First public template: five zones, short-noun router, install, architecture docs.
