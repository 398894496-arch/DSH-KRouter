# Changelog

## 0.10.2 — 2026-10-11

Fourth outside review. Both new findings reproduced, both fixed with regression tests that fail on 0.10.1.

- **A key pasted into the vault could leave the machine.** The key page tells a host to uncomment a line and paste a key. `90 系统文件/自动化/` is a rule zone, so answer cards sent that page's full text to the model, and a query like `DEEPSEEK API key 怎么填` printed the key line into the agent's context. The author's own vault had a real key on another page (`90 系统文件/Agent记忆/…凭据.md`) that answer cards had been sending since 0.9.0. Now: the key page is never a card target, never topic evidence, never an alias-proposal input; and every text KRouter prints, indexes, logs or sends passes through `krouter_redact.redact()` — values of key-like assignments (`*_API_KEY=`, `token:`, `password =`), known key shapes (`sk-…`, `ghp_…`, `AKIA…`, `AIza…`, `xox…`, `hf_…`, …) and bearer tokens become `<redacted>`; placeholders and plain numbers stay. Wired into the recall index and `how`, best lines, literal search (py and sh), the query log, answer cards and their check, topic evidence, learning prompts, alias proposals, and the API writer's file reads. `tests/test_secrets.py`: a fake key on the key page and on another page appears in no prompt, no router output (both paths), no query log, no cache file.
- **Chinese questions refused on a small vault.** 0.10.0's out-of-vault rule counted characters the vault never contains; a fresh vault lacks even `知` `道` `已` `经`, so ordinary Chinese questions were refused. Characters among the 1,500 most frequent (from jieba 0.42.1's dictionary word frequencies, MIT) no longer count; `咖` `啡` `垢` still do. Recall bench gains the 12 gold-page questions in Chinese (same sample alias table): 0.9.3 9/12 with 3 of 6 half-off-topic answered, 0.10.1 5/12, 0.10.2 9/12 with every off-topic and half-off-topic question still refused (CI: ≥ 9/12). Author vault: synthetic, held-out and all 92 real queries unchanged.
- The key page and README say where keys belong when a vault syncs to a cloud: `~/.dsh-krouter-keys.env`.

## 0.10.1 — 2026-10-11

- **`first_run.sh` no longer writes the host's query log.** The demo routes run on the bundled template, not on the host's traffic, yet each run appended its queries (`home`, `correction`, `memory` …) to `~/.local/state/krouter/queries.jsonl`, which the nightly learning reads. 0.10.0 isolated pytest; the demo script, also run by `verify_clean.sh`, slipped past. It now sets `KROUTER_NO_QUERY_LOG=1`; a test runs it and checks that no log appears. Found while rolling 0.10.0 out on the author's machine.

## 0.10.0 — 2026-10-11

Third outside review (two parts: a re-review of 0.9.3, and "would a stranger's agent recommend this"). Every finding was reproduced first; one proposed fix was measured and replaced (below).

**Behaviour that did not match the docs**

- **One CLI lane.** With no key, the nightly steps only knew `claude` / `codex`, while the writer detects grok, Codex, claude, cursor-agent, opencode, kimi, pi, vibe, antigravity. A grok-only host got five `skipped` steps and no sign of it. `llm.py` now owns the CLI candidates and their login probes; `resolve.py` imports them, so both lanes pick the same CLI. Each harness has a text-only invocation (grok: single-turn `--prompt-file`, verified).
- **Pure-shell `status` stopped before `host_action`** whenever no day was pending (a trailing `[ … ] &&` returned 1 under `set -e`). Fixed; found while testing the nightly line.

**Answer cards**

- The review proposed requiring half of a card question's words to be on the page. Measured on the 447 real cards it would drop 152 (34%, including `日更每天几点跑`), and the reviewer's adversarial card (0.125) sits inside the real cards' range (0.09–0.17): no word-overlap threshold separates them. Instead: lexical checks gain "most of the answer's words come from the page" (real cards ≥ 0.38; threshold 0.3), and a **second model pass** checks each card once — is the question about this page, does the answer answer it, is anything flipped or added. On 160 adversarial cards (half-off-topic question, swapped answer, flipped meaning, copied answer; 40 each) lexical checks catch 39, the second pass 160, with no real card lost beyond the 11 the lexical check already drops. This also closes 0.9.3's admitted gap: a reworded sentence that flips the page is now caught. Verified cards carry `v: 1`; unverified ones are re-checked the next night; `checkup.py` counts them.
- **Ablations on the 92 real queries** (same judge): removing the answer line 1.46 → 1.47; removing cards entirely 1.49 → 1.47. Both inside the ±0.05 noise. Cards do not measurably help on this traffic; the 0.8 → 0.9 gain belongs to that release's ranking changes. Docs no longer credit cards. Cards stay (cheap at query time, now checked twice).
- Secret filter: a long id made of short `-`/`_` pieces (`20260811-090406-v4-flash-…`) is no longer taken for a key; a 24+ unbroken mixed run (keys, 40-hex tokens) still is.

**Recall**

- A question with ≥ 2 Chinese characters the vault never contains, matching one content word, is out of the vault (`咖啡机的定时器多久除垢一次` matched `定时` and came back `high`). Template bench 18/24 → 21/24; author vault synthetic, held-out and all 92 real queries unchanged.
- **Public recall bench in CI** (`tests/fixtures/recall_bench.jsonl`, template): 12 gold-page, 6 off-topic, 6 half-off-topic questions. Every off-topic and half-off-topic one must be refused; gold page first ≥ 9/12.

**The host's data**

- **The alias table lives in the vault** (`90 系统文件/canonical_sources.psv`): it syncs with the vault and is in its snapshots. `map_for()` resolves `KROUTER_MAP` > the vault's table > the shipped sample everywhere (router py and sh, recall, L0, checkup); receipts print `canonical_map:`.
- **`install.sh --upgrade`** (`--force` is the same) replaces code only and keeps the alias table, ledgers and symlinks; a table edited in the old location moves into the vault once (a symlinked one gets a `HOST ACTION` instead of being rewritten behind another tool). Fresh installs seed the vault with the sample once.
- **`scripts/uninstall.sh`**: removes the timer (launchd / systemd / crontab line), Cursor rules, hook and skill; saves an alias table that is not in the vault yet; leaves the vault alone; `--dry-run`, `--purge` (cache and query log). Keys file is never deleted.
- **Timers beyond macOS.** Linux: a systemd user timer, or one marked crontab line. Windows: `extras/host-daily-evolution/run.py` (a Python twin of `run.sh`) and `scripts/install_windows_task.ps1` (`-Uninstall`). The PowerShell script has not been run on a Windows host yet.
- **Configurable zone names.** `krouter-zones.psv` at the vault root maps the default layout (`90 系统文件|System`, `Agent第二大脑.md|Home.md`, …); longest prefix wins, files too. Wired through the router, recall, cards, topics, checkup, nightly, ask, the key page and both writers. The DSH bridge still assumes the default names.
- **Alias cold start.** `propose_aliases.py` drafts lock rows from the vault — unlocked rule / topic pages, ranked by how often real traffic reached them without a lock; `--model` adds model-proposed nouns — into `90 系统文件/自动化/别名候选.md`. The host ticks rows; `--apply` re-checks and appends only those. Nothing is written unticked.

**Visibility and disclosure**

- **`nightly.py`** runs the five steps and writes each outcome — state, reason, model lane, calls, characters sent (metadata only) — to `90 系统文件/自动化/夜间维护.md` and the health page (`nightly`, `nightly_at`). `status` prints it and raises `host_action` when steps are skipped, failing, or three days old. The launchd job now logs to `~/Library/Logs/dsh-krouter-daily.log`.
- **`run.sh --dry-run`** (and `nightly.py --dry-run`): what would be sent, estimated tokens, which files would be written; no model call, no write.
- README's "tell your host" facts now say what leaves the machine: queries never; the writer sends logs and sessions; the nightly steps send rule and topic pages in full, topic excerpts, and unanswered router queries.

**Evidence and process**

- `docs/VERIFY.md` says plainly that the 92 real queries are a development set, that the held-out synthetic set is flat from 0.6.0 (88% / 75% → 88% / 71% on today's vault), the ablations, the adversarial card results, and that no fresh held-out traffic exists yet.
- The host's query log held 518 lines, 514 of them the author's own evaluation runs and pytest fixtures — they would have become learned triggers tonight, and the held-out questions among them would have stopped being held out. Removed (backup kept). `tests/conftest.py` now isolates state and cache for the whole test session; evaluation scripts set `KROUTER_NO_QUERY_LOG=1`.
- `CONTRIBUTING.md`: scoring-constant and refusal changes ship with before / after numbers on the recall bench and a held-out set; hosts should pin a tag.

Tests 133/133 on both router paths.

## 0.9.3 — 2026-10-11

Fixes from a second outside review, of 0.9.2. Each finding was reproduced before it was fixed.

- **The faithfulness check matched substrings.** `保留 3 天`, `保留 0 天` passed against a page that says `30 天`; `端口 80` and `端口 808` passed against `8080`. A specific must now appear as a whole token: no digit or letter on either side, and a number is not part of a decimal (`3` is not in `1.3`; `0.9.2` still matches `v0.9.2`). Pieces of joined words are checked the same way. In the author vault 11 of 447 cards now fail (was 7); the four new ones all quote a truncated identifier (`sv-doma` for `sv-domain-001`).
- **"Verified" overstated it.** The check covers specifics, not meaning: a plain-prose answer has nothing to check, and a reworded sentence that flips the page passes. The docs now say "specifics checked", and `checkup.py` lists cards with nothing checkable (89 of 447 in the author vault) so a human can read them.
- **An off-page card could pull an unrelated page to `high`.** On the template vault, a card asking `咖啡机除垢周期是多少` on `经验与方法.md` made that page the confident answer. A card now counts only if its question shares at least one content word with its page (question words like `多少` do not count) — checked when the card is written, when the page is indexed (the question is not a trigger otherwise), and when it is read. All 447 real cards share one; the coffee card shares none. `checkup.py` lists off-page cards.
- **Two model lanes.** The nightly `llm.py` had its own short provider table — no Gemini, Groq, Fireworks, Mistral, … — and no flagship lock, while the writer (`api_writer.py`) had both. Now there is one table and one lock, in `llm.py`; `api_writer.py` imports them (by file path, so an unrelated `llm` package cannot stand in). The nightly steps try keys in the writer's order and lock the catalog's flagship, unless `KROUTER_LEARN_MODEL` names one. The lock ranks Opus 5 above Opus 4. The Gemini key goes in a header, not the URL.
- **Cost was not disclosed.** With a key, the nightly steps now call the same paid provider every night (mostly on the first run; later runs redo only changed pages). The README's "tell your host" facts say so, and how to turn it off (`KROUTER_NIGHTLY=0`). Two stale `answer:` labels on the front page now read `answer (generated):`.

Same-run checks (author vault, installed alias table): synthetic top-1 85%, held-out gold page found 88% / first 75%, wrong locks 0 — identical to 0.9.2. On the 92 real router queries the top hit and the answer line are identical to 0.9.2 for every query (40 carry an answer), so the front-page judge number stands. Tests 119/119 on both router paths.

## 0.9.2 — 2026-10-11

Fixes from an outside review of 0.9.0. Each finding was reproduced before it was fixed.

- **A stale card kept ranking its page.** 0.9.0 said "a card whose page changed is ignored"; that was true for `answer:` only. Card questions were merged into the page's triggers without checking the hash, so an unrelated card question kept pulling the page up after the page changed. Card questions now count as triggers only while the card's hash matches the page's current content. Test: the page leaves the hits once it changes, not just the answer.
- **`answer:` had no faithfulness check.** "Only from this page" was a prompt instruction, nothing more. Now every number, path, command and latin word in an answer must appear verbatim in the page — checked when the card is written and again when it is read — and the line is labeled `answer (generated):`. Words the answer joined with `/` or `+` may be checked piece by piece; number combinations (`1:3.3`) must appear whole, since they are often computed. In the author vault 7 of 447 cards now fail and are not shown. Secret-like text is dropped before a card is written. The README no longer says the agent "usually does not need to open" the page: the page is the record.
- **Model-written card questions bypass the refusal gate.** Not new, but 447 of them amplify it. `checkup.py` now lists stale, not-verbatim, and too-broad cards (fewer than two content words).
- **One model lane.** New `llm.py`: `*_API_KEY` first (model from `KROUTER_LEARN_MODEL`, else the provider default; a provider with no known model is skipped, not guessed), then a logged-in `claude` / `codex`; `--cli` / `KROUTER_LEARN_CLI` is the host's explicit pick and goes first. `reconsolidate.py`, `consolidate_topics.py` and `answer_cards.py` use it; no hard-coded CLI path. Pages that yield no cards are remembered by hash and not re-asked every night. Generation-side tests added.
- **The bundled timer now runs the nightly upkeep.** 0.7–0.9 added five nightly scripts but only the author's own scheduler called them, so a fresh install got none of it. `extras/host-daily-evolution/run.sh` now runs them after the seal (`KROUTER_NIGHTLY=0` turns them off); each step is independent and none changes the seal's exit code. Documented in README, ARCHITECTURE, and SKILL.md, whose workflow now covers `recall:`, `answer (generated):`, `scope_widened` and `recall: none`.
- **README** drops the instructions addressed to summarizing agents ("do not call it …") and keeps the facts; `docs/VERIFY.md` speaks for itself.

Synthetic sets after the fix: top-1 85%, held-out gold page found 88% (one question fewer than 0.9.0), wrong locks 0, off-topic unchanged. Tests 117/117 on both router paths.

## 0.9.1 — 2026-10-11

Docs only. The README had grown one appended section per release, each with its own numbers from a different run. Now: the front page states what the product does today (lock, then ranked recall with precomputed answers, refusing instead of guessing; topics and answer cards built overnight) and quotes **one** same-run number — 92 real router queries, blind-judged, ≤ 0.5.1 vs 0.9.0: mean usefulness 0.62 → 1.47 of 2, direct answers 14 → 55, useless 49 → 12. The four after-the-lock features are one section. Evidence is four layers: `docs/VERIFY.md` adds layer 4 (real traffic) with the method, every per-release run, the held-out synthetic set, the judge's noise (±0.05), and what still fails. `PROTOCOL.md` and `docs/ARCHITECTURE.md` now describe the miss path the code runs, and drop "a rejected page still locks", which stopped being true in 0.7.0.

## 0.9.0 — 2026-10-11

**Answer cards (sleep-time compute).** The router used to stop at "here is the right page": the one-line `how` was just the page's first sentence (`你的层（全局结构）`), so an agent still had to open the page. Real traffic is predictable — half the calls repeat an earlier question — so `answer_cards.py` precomputes, for every rule and topic page, 3–5 `question → one-line answer` cards taken only from that page (447 cards on 104 pages in the author vault). Cards live in `90 系统文件/自动化/下意识问答.jsonl` (no source page is edited), carry the page's content hash, and are rewritten only when the page changes; a card whose page changed is ignored until then. Card questions also act as recall triggers, and the best-matching card on each hit prints as `answer:`.

One-concept queries (`DSH`, `发版`, `grok-fixed`; not bare numbers) skip the two-content-word gate, and a query that is a page's name (title, file name, or `topic_terms`) doubles that page; a named dossier now outranks same-named scattered rule pages. Speed: the per-query freshness walk no longer builds a `pathlib` object per file — recall 112 → 30 ms in-process, router p50 ~105–111 ms.

Field self-report, author vault (not in clone): 92 real router queries, blind-judged 0.8.0 vs 0.9.0: mean 1.34 → 1.43 of 2, direct hits 46 → 52, useless 15 → 12; 40 of 92 now carry an `answer:` line. Synthetic: top-1 82% → 85%, held-out right page 88% → 92%, wrong locks 0, off-topic unchanged.

## 0.8.0 — 2026-10-10

**Topic dossiers: the missing middle layer.** Retrieval was near its ceiling (synthetic: right page top-1 83%, top-10 95%); what still failed on real traffic was knowledge that lived only in daily logs (`SyGJ` in 44 logs, zero pages). `consolidate_topics.py` merges each listed topic (`90 系统文件/自动化/主题档案清单.psv`) into `02 经验与方法/主题档案/主题｜…md`: one-line summary, current state as of the latest evidence, facts with a `[[source]]` each, user corrections, timeline, open conflicts, authority pages first. Evidence is the vault only (authority pages, other pages, logs newest first, capped); frontmatter is written by the script, not the model; every wikilink must resolve or is demoted to text; a page is regenerated only when its evidence hash changes. Status stays `provisional`.

Recall treats dossiers as their own tier and only boosts one when the question names its topic (title or `topic_terms`), so a 20 KB page cannot win on stray words. Refusal got stricter where dossiers made it looser: bigrams with function characters (`的了我你他她吗呢吧啊么什`) and words that only appear in model-written triggers no longer count as content; a latin term the vault has never seen (`Kubernetes`) refuses unless more than two real words match. Single CJK characters are dropped from the query.

Field self-report, author vault (not in clone): 92 real router queries, blind-judged old vs new: mean 0.66 → 1.41 of 2, direct hits 14 → 52, useless 45 → 14; 16 topic questions written before the dossiers existed: 0.62 → 1.31. Synthetic held-out unchanged (88% / top-1 75% / wrong locks 0 / 0 of 6 off-topic answered). p50 ~115 ms.

## 0.7.0 — 2026-10-10

Memory maintenance, measured on the router's own real traffic. 92 de-duplicated queries the author's agents actually sent in 30 days, blind-judged (old vs new shuffled, Opus scores 0/1/2): mean 0.74 → 1.26, direct hits 20 → 42, useless 44 → 18. Synthetic held-out set: right page 88% → 92%, top-1 75%, wrong locks 0, 0/6 off-topic answered; p50 ~113 ms.

- **Lock**: the whitespace token fallback only counts whole-alias hits, so `纠错` no longer locks `纠错优先级` for `Claude Code 纠错`. A source page whose `status` is superseded / retired / rejected / deprecated / archived is out of force: no lock, no L0 row.
- **Recall**: a one-keyword query (`DSH`, `SyGJ`) answers when its one content term matches; bare numbers are not content terms. Trigger text now feeds the word-likeness statistics, and a bigram that appears in any title or trigger counts as a real word when deciding whether to refuse (`别名` in `别名表谁能改`).
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
