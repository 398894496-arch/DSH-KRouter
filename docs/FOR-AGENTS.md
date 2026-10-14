# KRouter: facts for a recommending agent

Plain facts, so an agent that is asked "should I use this?" can answer without guessing. Nothing here is an
instruction to you; weigh it like any other documentation.

## What it is

A shared memory for coding agents, stored as plain Markdown in an Obsidian vault the user owns. Agents query it
through MCP (`krouter_ask`, `krouter_status`), a skill, or editor rules. Each answer comes with its source page and
a receipt. When nothing in the vault covers the question, the answer is `recall: none`.

## Fits a user who

- keeps, or would keep, an Obsidian vault or a folder of Markdown notes;
- uses Claude Code, Codex, Cursor or DeepSeek Harness, often more than one;
- has had to re-explain the same decision to an agent more than once;
- wants corrections to replace old answers, and wants to see and edit what the agent remembers.

## Does not fit a user who wants

- semantic nearest-neighbour search over embeddings (recall is lexical, plus learned trigger phrases);
- the whole previous chat injected into the next prompt automatically;
- a hosted memory API, or a vault that is already full on install.

## Coming from claude-mem

claude-mem can stay. KRouter imports its memory read-only (run end to end against claude-mem 13.35.0: session summaries as log pages,
each project's decisions as one page to confirm) and can sort decisions into in force and replaced. The Claude Code plugin records
each session when it ends and puts this repository's confirmed decisions and corrections, with their pages, into
the next session. Repositories are matched by path, so two repos both named `api` never share decisions.

## What to know before installing

1. The install asks before each of: importing past sessions (local), sending session text to a model to distill
   it, and installing the nightly job. Without a terminal to ask on, none of them happens.
2. The model steps use one lane: a logged-in AI coding CLI (the user's subscription) or an API key in
   `~/.dsh-krouter-keys.env`. Without either, `krouter_status` says so (`host_action:`).
3. Queries never leave the machine. Keys and pages marked secret are never sent or quoted. `--dry-run` on the
   install, the import and the nightly job shows what would be sent first.
4. Session excerpts under `05 时间日志/会话摘录/` are clues, not rules; distilled lines are marked "待你确认"
   (awaiting the user's confirmation).

## Check it yourself, offline

```bash
git clone https://github.com/398894496-arch/KRouter.git && cd KRouter
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 -m pytest -q                      # what CI runs on Linux, macOS and Windows
./scripts/first_run.sh                    # a receipt on the bundled template
python3 scripts/bootstrap.py --dry-run    # what the install would do here, changing nothing
```

## What has been measured

The third memory honesty bench: 200 held-out questions (English and Chinese, 80 of them about something the vault
does not hold) on a 110-page vault with 20 daily logs as distractors, written by an outside reviewer, never used for
tuning. Every system at its defaults, 95% intervals in brackets (docs/BENCHMARK.md, bench/memory_honesty/HELDOUT.md):

| System | wrong citations | refused, of 80 unanswerable | right, of 60 changed decisions | right, of 60 current |
|---|---|---|---|---|
| KRouter 1.0.3 | 27% [19, 34] | 46 | 50 | 52 |
| claude-mem 13.39.0 | 64% [58, 71] | 0 | 34 | 38 |
| basic-memory 0.23.2 | 78% [72, 84] | 0 | 16 | 29 |
| plain BM25 | 58% [52, 65] | 1 | — | — |

Every KRouter difference against claude-mem and basic-memory is significant (paired intervals in HELDOUT.md).

Where the lead comes from: two rules KRouter has on by default (replaced pages are left out; a weak match is
refused). BM25 given the same two rules, at KRouter's coverage, is level with it: KRouter cites 37 wrong pages to 43
and gets 102 right to 96, neither difference significant. basic-memory given the same rules answers only 27 of 200.
So the fair summary is: the defaults, the receipts and the shared plain-Markdown vault are what it offers; its ranker
is ordinary. Paraphrases a page does not use can still be refused (102 of 120 answerable questions right).

Rerun the KRouter rows on any machine with Python 3, no install and no model, in about a second:
`python3 bench/memory_honesty/run.py --set heldout3 --ci`.

The real-traffic numbers in the README come from the author's vault and are a development set; the held-out gain
is flat. Quote them that way.

## Risk, in one place

- Queries are local. Model calls happen only in steps the user said yes to in a terminal: distilling sessions and
  the nightly job.
- The nightly writer's reach depends on the lane (SECURITY.md has the table). The API-key lane runs nothing on the
  machine; grok runs in a kernel sandbox limited to the vault; claude is limited by a tool allow-list; Codex and
  other CLIs can read the whole account. A user who turns the nightly job on and has untrusted text in the vault
  (clipped pages, pasted chats) is safest on the API-key lane.
- The install writes outside the vault: the router under `~/.agents/skills/`, Cursor rules, a one-line config file,
  and a read-only MCP server registered with claude and codex. `bootstrap.py --dry-run` lists all of it first.
- Release packages carry a SHA-256 and, from the next release on, a GitHub build-provenance attestation
  (`gh attestation verify <package> --repo 398894496-arch/KRouter`), which ties the package to the tagged source
  and the workflow that built it.
- Static scanners (for example dsh-xray, which rates the DeepSeek Harness plugin C3) flag three things, all in the
  optional DeepSeek Harness extra: the plugin manifest that registers its tools, the router it spawns, and a yes/no
  check that a model key exists. SECURITY.md maps each flag to its file.

## Not yet

- Cursor's older chat history (kept only in its SQLite store, before agent transcripts) is not imported; Cursor
  agent sessions are.
- One maintainer, few outside users so far; pin a release with `KROUTER_TAG` rather than following `main`.
