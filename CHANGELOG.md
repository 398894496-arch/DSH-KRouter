# Changelog

## Unreleased

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
