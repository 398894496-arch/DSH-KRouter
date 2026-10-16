# Held-out set: rules and log

`heldout.jsonl` holds 25 questions on the same 30-page vault as the development questions (`questions.jsonl`):
9 `correction`, 6 `current`, 10 `refuse` (neighbour questions). Same schema, ids prefixed `H-`.

The development questions are what KRouter is tuned on. These are not. Their only job is to say how KRouter does on
questions nobody shaped it for, so the number is worth something only as long as nobody tunes toward it.

## Where the questions come from

**Who the "outside reviewer" is.** Every held-out set here, and the outside reviews in `CHANGELOG.md`, come from
Claude Opus in claude.ai chat sessions that the maintainer starts and relays: not a human, and not the Claude Code
sessions that change KRouter, but the same model family. "Outside" means a separate session that did not write the
code it reviews; it does not mean independent of Anthropic's models, so question wording may share that family's
habits. A set written by a person is planned and will be logged here before it is run.

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
| 2026-10-12 | Applied by the maintainer's Claude Code session (the one that changes the ranker). The file was decompressed only by code: a count of rows and a scan for key-shaped text, nothing printed; the session did not read the questions. Aggregates only, matching the baseline (KRouter 33%, 9 / 20, 24 / 30). |
| 2026-10-12 | Maintainer's session: dense-retrieval prototype (`dense.py`, local multilingual MiniLM via fastembed) tuned on dev3 only. Candidate pre-registered on dev3 before the run: `agree` (BM25 over character pairs and dense must agree on the top page, both skipping superseded pages, floors picked on dev3). One heldout2 run, aggregates only: `agree` 18% wrong citations (5 / 28), 15 / 20 refused, 23 / 30 right. Also reported, not used to choose: `dense` 23% (7 / 30), 13 / 20, 23; `vote` 27% (10 / 37), 10 / 20, 27; KRouter 1.0.3 33% (12 / 36), 9 / 20, 24; bm25-floor 19% (4 / 21), 16 / 20, 17 (the freeze table says 5 / 22, 15 / 20; the one-question difference is under investigation). No `--reveal`. |

## Held-out set 3 (`heldout3.jsonl.gz`)

200 questions on a third vault, `vault3/`, and **no development set on that vault**: nobody tunes on vault3, so it
measures what a vault KRouter has never seen gets, which is every new user's vault. All rules above apply.

**The vault.** 110 pages: 30 English rule pages under `Handbook/` and 30 Chinese under `团队手册/` (15 of each were
replaced, and their 30 old pages say `status: superseded`), plus 20 daily logs (`Daily log/`, `工作日志/`) that
mention old decisions and open discussions in passing. The logs are distractors: they are never a gold page, and
citing one first counts as a wrong citation. Real vaults are full of such pages; vault1 and vault2 had none. The logs
sit in plain folders, not in KRouter's `05 时间日志/`, so no system gets a head start from the layout.

**The questions.** 100 English and 100 Chinese: 60 corrections, 60 current, 80 neighbours (40%). Two answerable
questions per rule page, on different facts or in different words. Same checks as set 2, run by script before any
system was run: every answerable question's `evidence` sentence is on its gold page; every neighbour question's
`absent` term is in the question and on no page of vault3, logs included, English plurals counted. Before the first
run the checker was tightened (plurals) and two Chinese neighbour questions had their `absent` term set to the
question's own wording; no question text changed. Written on 2026-10-13 (Pacific) by the same outside reviewer, who
had not read the code of `feature/dense` or the logistic-regression work, and knew of them only from the maintainer's
summary (method names and dev3 / real-vault aggregates). Stored gzipped, as set 2.

**What it is for.** Enough questions to tell systems apart: with 50 questions the 95% intervals of a wrong-citation
rate are about ±15 points wide, here about ±7. `run.py` gives bootstrap intervals (`--ci`), paired intervals against
another system (`--vs`), a comparison at the same coverage (`--vs-matched`), and the coverage curve (`--curve`).
All four are aggregates and may be run on this set.

**Baseline at freeze** (main `792c74e`, KRouter 1.0.3; `bm25-floor` uses the floor picked on dev3, since vault3 has no
dev set). 95% bootstrap intervals in brackets.

| System | wrong citations | neighbours refused (of 80) | answerable right (of 120) |
|---|---|---|---|
| Plain BM25, always answers | 58% (116 / 199) [52, 65] | 1 [0, 3] | 83 [69, 96] |
| BM25 + skip superseded + floor from dev3 | 21% (18 / 85) [13, 30] | 64 [52, 78] | 67 [54, 80] |
| KRouter 1.0.3 | 27% (37 / 139) [19, 34] | 46 [35, 58] | 102 [88, 116] |
| BM25 + skip superseded, **same coverage as KRouter** (top 139) | 31% (43 / 139) | 44 | 96 |

KRouter 1.0.3 minus BM25 at the same coverage, paired 95% intervals: wrong-citation rate [-10.2, +1.4] points,
answerable right [-2, +14], neighbours refused [-7, +11]. Better on every point estimate, and not yet significant on
any. Along the whole coverage curve KRouter cites fewer wrong pages than BM25 at each coverage measured (for
example 19 vs 23 wrong at about 100 answered); its default threshold sits at the permissive end of its curve.

**Pre-registered decision rule** (written before any candidate is run on this set; amend only before a run, and log it).
A candidate is run on heldout3 once, at the default it would ship with.
1. **"Surpasses BM25"** may be claimed only if `run.py --set heldout3 --vs-matched bm25-floor` gives a paired 95%
   interval for the wrong-citation-rate difference entirely below zero, and an interval for the answerable-right
   difference that is not entirely below zero.
2. **Ships as the new default** only if, on heldout3, its wrong-citation rate is at most 27%, it refuses at least 46 of
   80 neighbours and gets at least 97 of 120 answerable questions right (1.0.3 minus 5), **and** the time-split blind
   judge on real traffic does not fall more than 0.05 below 1.0.3. Rule 2 does not need rule 1.
3. At most two candidates per release cycle are run on heldout3; each run is a line in the log below.

### Log, set 3

| Date | Event |
|---|---|
| 2026-10-13 | Vault3 and heldout3 written by the reviewer; checked by script; frozen; first run, **aggregates only** (KRouter 1.0.3, BM25, BM25-floor, with intervals, the matched comparison and both coverage curves; table above). No `--reveal`. Not a candidate run. |
| 2026-10-13 | Applied by the maintainer's Claude Code session. heldout3 was decompressed only by code (row count, key-shaped-text scan, nothing printed); the questions were not read. Not a candidate run. |
| 2026-10-14 | **Other memory systems on heldout3, registered before the run** (not candidates; the two-candidate limit does not apply). basic-memory 0.23.2 (latest on PyPI), in the container (`adapters/Dockerfile`), its default search, top 3 (in 0.23 that is hybrid: full text plus semantic search with fastembed `BAAI/bge-small-en-v1.5`, min similarity 0.55, reranker off; the container runs offline, so the model is downloaded on the host and mounted; added before any heldout3 output was scored); a question counts as refused only when the search returns nothing. Scored twice: at its default, and with the two rules from `floor.py` (superseded pages skipped, floor picked on dev3 on vault2, applied unchanged). Aggregates only, `--ci`; no `--reveal`, and the adapter's per-question output is not read. mem0 and Zep / Graphiti are not run: both need a hosted model for extraction and none was configured for this run. claude-mem pending. |
| 2026-10-14 | **basic-memory 0.23.2 on heldout3** (as registered above; one run, aggregates only, no `--reveal`; a mechanical check found every cited path is a vault3 file). Default: 77.5% wrong citations (155 / 200) [71.5, 83.5], 0 / 80 neighbours refused, 45 / 120 right (16 corrections, 29 current). With the two rules (floor 1.225 picked on dev3): 18.5% (5 / 27) [4.2, 33.3], 76 / 80 refused, 22 / 120 right. KRouter 1.0.3 minus basic-memory default, paired: wrong rate [−58.5, −43.4] points, right [+43, +72], refused [+35, +58]. On dev (vault1) 0.23.2 scored 18 / 29 wrong against 0.22.1's 11 / 28. |
| 2026-10-14 | **claude-mem on heldout3, registered before the run** (not a candidate). The latest claude-mem from its marketplace, at its defaults (observer `claude-haiku-4-5`), in an isolated HOME with `CLAUDE_MEM_CLAUDE_CONFIG_DIR` set so it cannot reach the host's keychain login (C50). It learns vault3 as in the first bench: Claude Code sessions (model haiku) in a copy of vault3 read every page, one Read per page, one session per top folder, with a neutral prompt (read and list each page's rule or entry); then each question goes to its `/api/search`, top 3, mapped to pages through `files_read`. A question counts as refused only when nothing maps to a page. Default only (it gives no score, so no floor). Aggregates only, `--ci`; no `--reveal`, and the adapter's per-question output is not read. |
| 2026-10-14 | **claude-mem 13.39.0 on heldout3** (as registered above; one run, aggregates only, no `--reveal`). Four haiku sessions read all 110 pages (45 + 45 + 10 + 10 Read calls, no errors); its observer, signed in through the environment token only (the keychain lookup went to the isolated service name and found nothing), stored 85 observations covering 85 of the 110 pages and skipped 18 reads as noise; queue drained before any question. Every cited path is a vault3 file. Default: 64.0% wrong citations (128 / 200) [57.5, 71.0], 0 / 80 neighbours refused, 72 / 120 right (34 corrections, 38 current). KRouter 1.0.3 minus claude-mem, paired: wrong rate [−45.0, −29.9] points, right [+17, +44], refused [+35, +58]. The isolated directory was deleted afterwards. |

## Held-out set 5: real questions from the maintainer's own agents (registered 2026-10-16, before any run)

**Where the questions come from.** Everything the maintainer typed to seven agents between 2026-06-09 and 2026-10-16,
read from each agent's local store by `bench/real_questions/extract_asks.py`: Claude Code (session files and the
prompt history), Codex (current and restored archives), Cursor agent transcripts, DeepSeek Harness (personal and
company), Grok and Hermes. Human messages only (no injected context, tool output, subagents, headless or automation
runs), redacted, de-duplicated: 11 853. A rule prefilter kept 5 369 question-like ones. Grok 4.7 (high reasoning,
through the maintainer's CLIProxyAPI) labelled each: 393 ask about something the maintainer or their agents had
decided, set up or done (`classify_asks.py`). One more Grok 4.7 call over all 393 marked 332 as understandable without
their conversation and grouped them by intent into 208 things (`group_asks.py`). The frozen set is the earliest ask of
each group: **208 questions**, all Chinese (74 from June, 15 July, 63 August, 44 September, 12 October), SHA-256
`ed2efd001e9a32d6a522fbb0d9a8cf39e769917f3e67b8651de981f22152c61f`. Groups asked on two or more days give **38 pairs**
(earliest and latest ask) for the learning bench, SHA-256 `e2a8cb06c727d7a7161ab2460a58a79ac113b823d70bb44b8a20e121bdb0b84f`.
The questions are the maintainer's private messages: they stay on the machine and are never committed; only
aggregates are published. They were never used to tune KRouter (the 92 router queries of VERIFY.md layer 4 are a
different source). One known overlap: the alias table's 26 seed rows (2026-08-21) were written from 25 of the
maintainer's earlier questions, so some questions may hit an alias; hit modes are reported separately (below).

**Snapshot.** The maintainer's vault at its own git commit `57b6019` (2026-10-15), exported with `git archive`
(uncommitted edits are not used). 531 pages.

**Systems.** (a) KRouter on main `bf476ae` as an agent calls it: `route_knowledge.py search <question>` (alias lock,
then ranked recall), cited pages read off the receipt (`run_real.py`). (b) BM25 over character pairs and words,
superseded pages skipped, refusal floor picked on dev3. (c) Dense candidate 1 (`feature/dense` at `4412acd`, local
embeddings on, balanced tier). The SessionStart fix in #52 does not touch retrieval.

**Two configurations.** *As used*: the snapshot unchanged. *Without learning*: the snapshot minus
`90 系统文件/自动化/下意识触发词-自学习.psv` (6 learned lines); the alias table is kept, because all of its 167 aliases are
the 2026-08-21 seed (checked against the alias ledger: none added since). **The pass lines below use only *without
learning*.**

**Hit mode,** recorded per question and system: `canonical_match` (the alias lock), `learned trigger` (KRouter's
cited pages differ between the two configurations), `recall`, or `none` (refused). Reported separately.

**Valid citations.** A cited page counts only if it existed before the question was asked and does not come from the
question's own session or a later one. Evidence that a page existed: it is in the newest vault backup taken before the
ask (backups exist for 2026-08-18, 08-19 and 08-22), or its own date (frontmatter `created` / `date`, or a dated file
name) is earlier than the ask's day. Session excerpts and time logs dated on the ask's day or later never count. A
page with no such evidence counts as not having existed (score 0): 288 of the 531 pages carry no date, which weighs
most on asks before 2026-08-18; scores are also reported by month.

**Judging.** Grok 4.7, high reasoning (not a Claude model: KRouter was built and tuned with Claude). Per question the
judge sees the question, its date, and each system's output rendered the same way (each valid cited page's path,
date, status and first 400 characters; or "refused"). First it decides, from a candidate pool (all systems' cited
pages plus each system's top 5 without its refusal gate, each with date and status), whether the snapshot holds a
page that answered the question before it was asked. If it does, a refusal scores 0. If it does not, a refusal scores
2 and any citation 0. Otherwise each output scores 0 (useless), 1 (relevant, the agent still has to dig) or 2 (answers
it). Pairs are judged twice, the second time with X and Y swapped; a question's score is the mean.

**Agreement.** The maintainer labels 40 to 50 of the questions (a random sample, seed 20261016) without seeing the
systems' names; the report gives Grok's agreement with them (same score, and within one point).

**Pass lines** (*without learning*). "KRouter answers real questions better than BM25 with the two rules" may be said
only if the paired bootstrap 95% interval (10 000 resamples, seed 0) of KRouter minus BM25's mean score is entirely
above zero. For the dense candidate, this counts as the second piece of evidence for shipping it as an opt-in (with the
real-traffic blind judge registered above) if its mean is at most 0.05 below KRouter's.

**What any claim says.** One person's questions, on one vault, over four months and seven agents; that person is the
maintainer.

**Not in this run.** The cross-system injection comparison (step 3) waits until #52's two regressions are fixed and
reviewed.

### Log, set 5

| Date | Event |
|---|---|
| 2026-10-16 | Registered (commit on `bench/real-questions`, before any run). |
| 2026-10-16 | **Run, as registered.** Snapshot `57b6019`. KRouter (main `bf476ae`) answered 173 of 208 and refused 35; *as used* and *without learning* gave identical results (the 6 learned triggers changed no answer; no question hit the alias lock). BM25 + two rules answered 186, refused 22. Dense candidate 1 (`4412acd`, 1 216 page vectors) answered 81, refused 127. Valid-citation rule: of KRouter's 173 answers, 82 cite at least one page that provably existed before the ask (June 1 of 59, July 0 of 13, August 41 of 53, September 30 of 38, October 10 of 10); BM25 99 of 186. |
| 2026-10-16 | **Judged** (Grok 4.7 high, 26 batches × 2 passes per pair, X/Y swapped, no failed batch). KRouter minus BM25 + two rules: 0.363 vs 0.252, paired 95% interval [−0.019, +0.243]: **the "better on real questions" line is not met.** Dense candidate minus KRouter: 1.231 vs 0.370, [+0.726, +0.995]: **its registered line (at most 0.05 below KRouter) is met**. How to read both: the judge found a pre-ask answer page for only about 5% of the questions (11 of 208 in pair 1, 10 in pair 2), so scores are dominated by the refusal rule (refusing scores 2 when nothing answered the question yet); the dense candidate refuses most. On the 8 questions where both passes found an existing answer: KRouter 0.75, BM25 1.12; dense 1.0, KRouter 1.0 (too few to tell apart). The main finding is not about ranking: when the maintainer asked about past decisions, the vault mostly did not hold the answer yet. Maintainer agreement sample (45, seed 20261016): pending. |
