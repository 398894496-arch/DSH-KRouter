# Security

DSH-KRouter reads and writes a personal knowledge vault and can hold model API keys, so this page says exactly
where data goes and how to report a problem.

## Where your data goes

| Data | Where it goes | When |
|---|---|---|
| Router queries and answers | Nowhere: a local SQLite cache under `~/.cache/krouter/` and a local query log under `~/.local/state/krouter/` | Every query |
| Yesterday's logs and sessions | The model lane you chose (a logged-in AI coding CLI, or an API key) | The nightly job, only if you turned it on |
| Rule and topic pages, topic excerpts, unanswered queries | The same model lane | The nightly job, only if you turned it on |
| API keys | `~/.dsh-krouter-keys.env` (mode 600). Never the vault, never a prompt, never printed | — |
| Pages named or marked as secret (凭据 / 密钥 / 钥匙 / credential / secret / password, or `secret: true`) | Nowhere: never sent, never quoted | — |

`extras/host-daily-evolution/run.sh --dry-run` lists what the next nightly run would send, with token estimates,
and sends nothing. The one-line install asks before it installs the nightly job; without a yes it is not installed.

**What a CLI writer can see.** When the nightly job uses a logged-in CLI (`claude`, `grok`, …) it runs inside the vault
with permission prompts skipped (Codex runs in a workspace-write sandbox). It can read any file in the vault, which is
why keys never live there. Text filters (`krouter_redact.py`) protect what KRouter itself prints and sends; they cannot
filter what an agent reads on its own.

**Known limits of the text filter.** An unlabeled key that is pure hexadecimal is not masked (that is how notes record
commits and digests), nor a key split into short hyphenated groups. Put keys in `~/.dsh-krouter-keys.env`, or keep them
on a page whose name says what it is.

## Integrity of what you install

The one-line install downloads a tagged release, never `main`, and checks the package's SHA-256 against the release's
`SHA256SUMS` before unpacking (releases from v0.11.2 on; older tags fall back to the source archive and say so).
`KROUTER_TAG=vX.Y.Z` pins one release.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Use GitHub's private report:
**Security → Report a vulnerability** on this repository. Include what you ran, what you expected, and what happened.
You will get an answer within a week; fixes ship as a patch release with the finding credited in `CHANGELOG.md`.
