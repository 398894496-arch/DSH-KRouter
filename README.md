# KRouter

**Your coding agents remember what you decided — and what you changed your mind about.**

Claude Code, Codex, Cursor and DeepSeek Harness share one memory: a folder of plain Markdown in [Obsidian](https://obsidian.md) that you can read and edit. Ask "how did we decide to ship?" and the agent answers with the page it came from. A correction replaces the old answer instead of competing with it. When the vault does not know, the agent is told so, rather than handed something close.

[![ci](https://github.com/398894496-arch/KRouter/actions/workflows/ci.yml/badge.svg)](https://github.com/398894496-arch/KRouter/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/398894496-arch/KRouter)](https://github.com/398894496-arch/KRouter/releases/latest) [![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE) · 中文：[`README.zh.md`](README.zh.md)

![Monday we decide A, Wednesday we change it to B, Thursday the agent answers B and cites the correction; a question the vault cannot answer is refused](docs/img/demo.gif)

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/398894496-arch/KRouter/main/scripts/bootstrap.sh | sh
```

Windows (PowerShell): `irm https://raw.githubusercontent.com/398894496-arch/KRouter/main/scripts/bootstrap.ps1 | iex` · Claude Code plugin: `/plugin install krouter --marketplace 398894496-arch/KRouter` (Claude Code 2.1.275 or later; from a shell, `claude plugin install krouter --marketplace 398894496-arch/KRouter` needs 2.1.292). Third-party marketplaces do not auto-update: run `claude plugin update krouter@krouter`, or turn it on in `/plugin` → Marketplaces → krouter → Enable auto-update.

Python 3 is the only requirement. The installer makes a vault (or uses yours with `--vault`, overwriting nothing), connects Claude Code and Codex to it through MCP, and then asks you two questions.

## Five minutes later

1. **"Import the agent sessions already on this machine?"** On a yes, the last 7 days of Claude Code and Codex sessions become pages, one per session: your questions and each turn's closing answer. Key-shaped text is redacted first, and nothing leaves the machine.
2. **"Have your model pull out what was decided?"** On a yes, the model you already use (a logged-in CLI or an API key) writes "what was decided, what changed" at the top of each recent session's page. The installer tells you how many characters that sends before it sends anything.
3. Ask your agent: *"what did we decide about X last week?"* It answers from the vault, names the page, and says plainly when the vault has nothing on it.

From then on a nightly job, which also asks first, imports yesterday, distills it, and keeps the vault tidy. Nothing needs maintaining.

## How it is different

| | KRouter | Typical agent memory |
|---|---|---|
| Where memory lives | Markdown pages you can open, edit, diff and sync | A database or vector store |
| After a correction | The new page replaces the old one, which is marked superseded | Old and new chunks both match; you hope the right one wins |
| When nothing matches | `recall: none` — the agent says the vault does not know | The nearest chunk, presented with confidence |
| Every answer | Carries its source page and a receipt | Usually unsourced |
| Who shares it | One vault for every agent on the machine (MCP, skill, rules) | Usually one tool |

**Coming from [claude-mem](https://github.com/thedotmack/claude-mem)?** Keep it. The importer has been run end to end against a live claude-mem 13.35.0 install. The installer finds its memory and offers to import it: session summaries become pages, and each project's decisions become one page you confirm. Your model can then sort those decisions into the ones still in force and the ones a later decision replaced, which claude-mem itself does not do. The Claude Code plugin also does what makes claude-mem feel like memory, in plain Markdown: when a session ends it is recorded, and when a new one starts, this repository's confirmed decisions and recent corrections come with it, each naming its page. Repositories are told apart by their path, never by folder name. Both happen only after you said yes to importing.

## What leaves your machine

Queries never do: lookup is a local SQLite full-text index, about 110 ms. Session import is local. Text goes to a model only for the steps you said yes to: distilling sessions and nightly upkeep. It goes to the CLI or API key you already use, and `--dry-run` shows the size first. Keys and pages marked secret are never sent or quoted. Details: [`SECURITY.md`](SECURITY.md).

## Honest numbers

| Measured | Result |
|---|---|
| Refuses instead of guessing (public benches, CI) | Off-topic questions refused 12/12 (English) and 6/6 (Chinese) |
| Wrong citations on questions it was never tuned on ([memory honesty bench](docs/BENCHMARK.md), 25 held-out questions) | At their defaults: KRouter 25%; basic-memory 60%, claude-mem 60%, plain full-text search 61%; neighbour questions refused 8 / 10 vs 0, 0 and 1. **But the gap comes from two rules, not the ranker:** give plain search or basic-memory the same rules (leave replaced pages out, refuse below a floor picked on the dev set) and they reach 19% and 30%, and at the same coverage they cite slightly fewer wrong pages than KRouter. KRouter has both rules on by default |
| Exact match vs embeddings on a supersede / neighbor set (CI) | Exact match refuses where TF-IDF, MiniLM and BGE-M3 cite a neighbor |
| Real traffic, author's vault | 0.62 → 1.47 of 2, blind-judged. **This is a development set**: on held-out questions the gain is flat. A blind test on fresh traffic runs 2026-10-16 |

Methods and what still fails: [`docs/VERIFY.md`](docs/VERIFY.md).

## More

- [How it works, every option](docs/DETAILS.md): install flags, the nightly writer, exact match and ranked recall, answer cards, the four agent mounts
- [`SECURITY.md`](SECURITY.md): what each model lane can see and do
- [`docs/FOR-AGENTS.md`](docs/FOR-AGENTS.md): facts for an agent deciding whether KRouter fits its user
- [`CHANGELOG.md`](CHANGELOG.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md): good first issues are labeled

*Formerly DSH-KRouter. Old links, clone URLs and install lines still redirect.* MIT.
