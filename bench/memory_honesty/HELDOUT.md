# Held-out set: rules and log

`heldout.jsonl` holds 25 questions on the same 30-page vault as the development questions (`questions.jsonl`):
9 `correction`, 6 `current`, 10 `refuse` (neighbour questions). Same schema, ids prefixed `H-`.

The development questions are what KRouter is tuned on. These are not. Their only job is to say how KRouter does on
questions nobody shaped it for, so the number is worth something only as long as nobody tunes toward it.

## Where the questions come from

- Written on 2026-10-11 (Pacific) by Claude, an AI reviewer working for the maintainer in an outside review session,
  against the bench vault as of KRouter 1.0.0 (`c555de1`).
- Before writing them the reviewer had read the vault pages and the 30 development questions (to avoid duplicates).
  KRouter had not been run on any of them.
- Not edited after the first run. `H-R6` ("How should release tags be named?") is arguably borderline: the release
  page says to ship "from a tag on main" but says nothing about naming. It is kept as written, because editing a
  question after seeing results is exactly what this file forbids.

## Rules

1. **Frozen.** Questions, golds, kinds and the bench vault do not change. `tests/test_memory_honesty_heldout.py` pins
   a SHA-256 of `heldout.jsonl` and of the vault. A question found to be wrong is not fixed: the set is retired and
   a new one is added (rule 5).
2. **Not a tuning target.** A change to ranking, refusal or card checks justifies itself on the development benches
   (`questions.jsonl`, `tests/fixtures/recall_bench*.jsonl`), as `CONTRIBUTING.md` says. A PR may report the
   held-out aggregates; it may not use them as the reason for the change. CI has no floor on the held-out score, only
   a sanity guard far from any target: fewer wrong citations, and at least as many refusals, as plain full-text
   search that always answers.
3. **Aggregates only.** `python3 bench/memory_honesty/run.py --set heldout` prints totals, not which question was
   missed. `--reveal` prints the misses; use it only to audit a release, never while developing, and add a line to
   the log below when you do.
4. **Burned.** The set is burned if a ranking, refusal or vault change lands after a reveal by the same person, or if
   a change is shaped by known held-out misses. Then: add a line to the log, stop calling its numbers held-out, and
   rule 5 applies.
5. **Replacing it.** A new set (`heldout-2.jsonl`, same format, new pins) is written by someone who has not seen the
   ranker changes since the last set, before KRouter is run on it.
6. **Reporting.** Release notes and the README quote the held-out aggregates next to the development-set number,
   never the development number alone.

These rules make tuning toward the set visible; they cannot make it impossible. The pins and this log are the
guarantee: any edit to the questions, the vault or the pins shows up in a diff that a reviewer can ask about.

## Baseline at freeze

Frozen on 2026-10-12 at KRouter 1.0.1 (`8c2e0cb`). 1.0.0 scored the same.

| System | Wrong-citation rate | Refused | Correction hit | Current hit |
|---|---|---|---|---|
| Plain full-text search (SQLite FTS5 BM25), always answers | 61% (14 / 23) | 1 / 10 | 4 / 9 | 5 / 6 |
| KRouter 1.0.1 | 25% (3 / 12) | 8 / 10 | 5 / 9 | 4 / 6 |

## Log

What has been seen, by whom. Append; never rewrite.

| Date | Event |
|---|---|
| 2026-10-11 | Written by the reviewer; first run on KRouter 1.0.0. The reviewer saw the per-question results. |
| 2026-10-12 | **Partial exposure.** The three wrong citations were described publicly in `docs/BENCHMARK.md` and the 1.0.1 changelog: `H-A4` (branch-name format → the date-format page), `H-R6` (release-tag naming → the release page), `H-R7` (checkout load budget → the performance-budget page). Which answerable questions were refused was not published. Treat a change aimed at shared words like "format", at release-tag naming or at page-load budgets as aimed at this set. |
| 2026-10-12 | Added to the repository and frozen at 1.0.1 (`8c2e0cb`). Baseline above. |
