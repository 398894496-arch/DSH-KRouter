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
| 2026-10-12 | Applied to the repository by the maintainer's Claude Code session (the one that changes the ranker). It checked the file's format, counts and that it holds no secrets, and ran aggregates only (25%, 8 / 10, 5 / 9, 4 / 6, matching the baseline). It did not read the questions or run `--reveal`. |
| 2026-10-12 | Maintainer's Claude Code session ran held-out **aggregates** for basic-memory 0.22.1 and claude-mem 13.35.0 through their adapters (`adapters/`), for docs/BENCHMARK.md. No `--reveal`; their per-question held-out output is kept out of the repository. |
| 2026-10-12 | Outside reviewer ran held-out **aggregates** for a baseline (BM25 + skip superseded + score floor) at several floors, reporting only the dev-picked one. Baseline only, no KRouter change. |
| 2026-10-12 | Maintainer's session ran held-out **aggregates** for the matched baselines (BM25 and basic-memory, skip superseded + dev-picked floor) and a coverage sweep of those two baselines to find their point at KRouter's coverage. Baselines only; no `--reveal`; no KRouter change. |
| 2026-10-12 | **Used for one go / no-go decision.** Maintainer's session tried a set of recall changes on branch `recall/paraphrase` (English stemming, following `superseded_by` to the newer page, a relaxed unknown-word refusal, a missing-topic refusal, English answer cards), tuned on `questions.jsonl` and a new maintainer-written `questions_dev2.jsonl`. One held-out run, aggregates only: worse than 1.0.3 (38% wrong citations without cards, 31% with, vs 25%; neighbours refused 5 / 10 vs 8 / 10). Not shipped. No `--reveal`. A further change chosen by held-out aggregates would be tuning on this set; the next claim of a ranking gain needs `heldout-2.jsonl` from someone who has not seen these changes. |

## Held-out set 2 (`heldout2.jsonl.gz`)

50 questions on a second vault, `vault2/` (60 pages: 30 English under `Engineering/`, 30 Chinese under `工程规范/`;
20 decisions that were replaced, each with its old page, and 20 that were not). A development set of 50 on the same
vault comes with it, `questions_dev3.jsonl`, to tune on. All rules above apply to set 2 unchanged.

**Why a second vault.** By 2026-10-12 the first vault carried 105 questions on 30 pages, its wording had been studied
closely, and a round of changes that improved both dev sets made held-out worse (log above). Questions on a vault
nobody has tuned against are the cleaner test, and half of it is Chinese, which most KRouter users write in.

**Where the questions come from.**
- Written on 2026-10-12 (Pacific) by the same outside reviewer as set 1, together with the vault and `questions_dev3.jsonl`,
  for the maintainer's request that an independent writer produce the neighbour questions.
- 100 questions in six strata (English / Chinese × correction / current / neighbour), split 50 / 50 between dev3 and
  heldout2 with a fixed seed (20261012), stratified, so the two sets are the same kind of question: each has 15
  corrections, 15 current, 20 neighbours, 25 English and 25 Chinese.
- Every answerable question carries the sentence from its gold page that answers it (`evidence`); every neighbour
  question names the page it borrows from (`neighbor`) and a term that appears on no page of the vault (`absent`),
  so a neighbour question cannot be answered by accident. Both are checked by `tests/test_memory_honesty_v2.py`.
- Checked by script before KRouter was run on any of them; one held-out question repeated a maintainer dev2 question
  word for word and was replaced before the first run. Not edited after the first run.
- What the reviewer knew when writing: the vault-1 questions (all three sets), and the one-paragraph description of
  the not-shipped recall changes in `docs/BENCHMARK.md` ("Tried and not shipped"). Not their code, and not their
  per-question effects.
- **Exposure.** The questions were written in the reviewer's session, which the maintainer can read. The file is
  gzipped so that the maintainer's Claude Code session does not meet a question in a grep or a diff; it should apply
  the patch without decompressing the file.

**Baseline at freeze** (KRouter at `main` `f9d0be9`, i.e. 1.0.3 plus docs; first run of any system on these questions).
On vault2 the BM25 baselines split Chinese into character pairs; `bm25-floor` picks its floor on dev3.

| System | heldout2: wrong citations | neighbours refused | answerable right | dev3: wrong citations | refused | answerable right |
|---|---|---|---|---|---|---|
| Plain BM25, always answers | 61% (30 / 49) | 1 / 20 | 19 / 30 | 55% (27 / 49) | 1 / 20 | 22 / 30 |
| BM25 + skip superseded + dev3-picked floor | 23% (5 / 22) | 15 / 20 | 17 / 30 | 4% (1 / 22) | 19 / 20 | 21 / 30 |
| KRouter 1.0.3 | 33% (12 / 36) | 9 / 20 | 24 / 30 | 24% (8 / 34) | 13 / 20 | 26 / 30 |

### Log, set 2

| Date | Event |
|---|---|
| 2026-10-12 | Vault, dev3 and heldout2 written by the reviewer; integrity checked by script; one duplicate of a dev2 question replaced; frozen; first run, **aggregates only** for KRouter, BM25 and BM25-floor (table above). The reviewer has not looked at per-question held-out results. |
