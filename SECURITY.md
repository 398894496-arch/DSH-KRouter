# Security

KRouter reads and writes a personal knowledge vault and can hold model API keys, so this page says exactly
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

**What the nightly writer can see.** It depends on the lane, and the install prompt says which one you are choosing:

| Lane | Runs on this machine | Can read | Can write |
|---|---|---|---|
| **API key (recommended)** | Nothing: a direct API call | — (KRouter sends only what `--dry-run` lists) | — |
| `grok` | grok, in a kernel-enforced sandbox profile (`strict` + the router) | The vault, the router, system paths | The vault, KRouter's cache and state |
| `claude` | Claude Code, with tools allow-listed (`dontAsk`): read / edit inside the vault, run the router, nothing else | The vault (tool-level rule, no kernel sandbox) | The vault |
| Codex | Codex in its `workspace-write` sandbox | **Your whole account**, keys file included | The vault |
| Others (opencode, kimi, …) | The CLI with no confinement KRouter can set | **Your whole account** | **Your whole account** |

The vault is where untrusted text arrives (clipped web pages, pasted chats), so a writer that can do more than
read and write the vault is one prompt injection away from acting as you. Prefer the API-key lane; if you use a CLI,
prefer grok or claude. Before 0.12.0 the claude and grok writers ran with permission prompts skipped and no
sandbox — able to read and write anything in the account; an outside review pointed this out and a test confirmed
it (grok read a file outside the vault through both its file tool and its shell; under the new profile it cannot).

Text filters (`krouter_redact.py`) protect what KRouter itself prints and sends; they cannot filter what an agent
reads on its own — that is what the sandbox and the allow-list are for.

**Known limits of the text filter.** An unlabeled key that is pure hexadecimal is not masked (that is how notes record
commits and digests), nor a key split into short hyphenated groups. Put keys in `~/.dsh-krouter-keys.env`, or keep them
on a page whose name says what it is.

**Long-lived CLI token.** For the claude lane, `claude setup-token` issues a token for unattended use; put it in
`~/.dsh-krouter-keys.env` as `CLAUDE_CODE_OAUTH_TOKEN=…` (the file is mode 600, never in the vault). KRouter passes it
only to the `claude` process. It avoids the logout that happens when another program (a proxy, another machine) holds
the same keychain login and spends its single-use refresh token.

## Integrity of what you install

The one-line install downloads a tagged release, never `main`, and checks the package's SHA-256 against the release's
`SHA256SUMS` before unpacking (releases from v0.11.2 on; older tags fall back to the source archive and say so).
`KROUTER_TAG=vX.Y.Z` pins one release. If the release has a checksum file, a failed download or a mismatch stops the
install; a release without one installs only with `KROUTER_ALLOW_UNVERIFIED=1`.

What the checksum does and does not prove: it is published in the same release as the package, so it catches a
corrupted or truncated download, not a compromised repository or release. For that, compare the package with the
tagged source yourself (`npm pack` on a checkout of the tag gives the same files).

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Use GitHub's private report:
**Security → Report a vulnerability** on this repository. Include what you ran, what you expected, and what happened.
You will get an answer within a week; fixes ship as a patch release with the finding credited in `CHANGELOG.md`.
