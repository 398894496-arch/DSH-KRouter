# Changelog

## Unreleased

- Public lock-vs-neighbor fixture, N=22. Claim A closed: supersede 4/4 old-page is `invalid_at`+map, not rankers. Claim B is refusal vs *unthresholded* cosine; a min_score sweep on tfidf_map does not match the lock (hit 10/10 and negative 4/4 miss). Not LongMemEval; not dense retrieval.
- The template ships both rungs of the ladder: one `active` method and one `provisional` draft, routed as Q09 and Q10. Ten sample nouns now, delete them when your own land.
- Two SVGs in `docs/img`: a receipt on a hit next to a miss with hints, and what the vault holds on clone versus after two weeks.
- A latin fragment of an alias is not a canonical hit. A shorter latin query has to carry the alias; one CJK character still does. Checked against 167 live aliases: no behaviour change on any of them.
- README lead is now host-facing: second brain, daily distill as remembering, clone is the OS. Agent anti-summary is a one-line callout plus a bottom table, not the first screen. Reviewers get a recommend/do-not-recommend rubric, a receipt sample, and the alias row to copy.
- Self-evolution key lives on the vault page. **API key first** locks that provider's flagship model (`api_writer.py`). **No key** uses the user's Claudian-class CLI subscription. Both lanes distill and write `provisional`. Placeholders only in git.
- Subscription unattended: a logged-in Claudian-class CLI (`grok` / official Codex / `claude`, …) distills without a person at the prompt. Grok uses `--permission-mode bypassPermissions` (Claudian yolo); Claude `--dangerously-skip-permissions`; Codex `exec --sandbox workspace-write`. The timer pins this clone's `krouter-obsidian`, not a live `obsidian-knowledge-router`. CLI cancel/empty still writes `待总结`.
- One local product: DSH-KRouter. `extras/dsh` is the DSH socket; `extras/host-daily-evolution` is the writer (`wire_keys.py` graft: logged-in CLI or `*_API_KEY`). Not two projects.
- Key and CLI probing live once in `resolve.py`; `wire_keys.py` is only the installer front end. The timer reads keys from the process env, `~/.dsh-krouter-keys.env`, and the vault page (page wins).
- API lane is covered end to end on a loopback stub: catalog, flagship lock, bearer header, seal on disk, and `待总结` on a failed call. The router entry falls back to `grep` when `ripgrep` is absent.
- `status` prints `host_action` while the key and CLI login are missing. Cursor / Codex / Claude mounts must tell the host. `install.sh` will not load the timer onto the clone template.

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
