# Host daily evolution (the writer)

This is the **product**, not a side plugin. It is the writer socket of **DSH-KRouter** (same tree as `extras/dsh`). Self-evolution: seal yesterday’s log, distill, **write `provisional` the same day when the five gates pass**.

Timer is **on by default** (`lamp: running`). **API key first:** lock that provider's flagship model, then distill and promote. **No key:** the user's Claudian-class CLI subscription does the same work. `lamp: unused` = you turned the timer off.

The job auto-detects the CLI each run. Keys come from the vault page, `~/.dsh-krouter-keys.env` (what `install.sh` writes), or the job environment — the vault page wins. Do not commit a live key.

| File | Role |
|---|---|
| `check.sh` | Proves writer files exist and reads `lamp:`. Default `running`. Does not fire the job. |
| `run.sh` | OS job entry. Calls `resolve.py --exec`. Skips distill if the key and CLI login are both missing. |
| `resolve.py` | The one probe engine: collects keys (process env, `~/.dsh-krouter-keys.env`, vault page — page wins), detects a logged-in CLI, otherwise runs the bundled API writer. Never prints secrets. |
| `api_writer.py` | Distill with only an `*_API_KEY`. No grok / Codex / claude required. |
| `wire_keys.py` | Installer front end over `resolve.py`: detect a logged-in CLI (`--detect`), probe keys, keep the live ones in `~/.dsh-krouter-keys.env`. Never copies `auth.json`, never writes the vault. |
| `patch_health.py` | Updates health fields (`present` / `missing` / `dead` / `unknown`). Never the secret. |
| `PROMPT.md` | Writer contract. Passed to the detected CLI. |
| `launchd.example.plist` | macOS example. `OBSIDIAN_VAULT`, `KROUTER_ROUTER`, `HOME`, `PATH` (includes `~/.grok/bin`). No key slot. |
| `cron.example` | cron example. Same. |

`dsh plugin add` is a mount, not this writer. It does not replace the timer.

## Prove it on the template

```bash
export OBSIDIAN_VAULT=/path/to/DSH-KRouter/template
./extras/host-daily-evolution/check.sh
```

`./scripts/first_run.sh` runs that check. Pass means the writer files exist, the key page ships placeholders only, and the lamp is `running` (default) or `unused` (you turned it off). CI does not fire the daily job.

## Contract

1. Set `OBSIDIAN_VAULT` to your vault root (copy `template/` there first).
2. **API key first.** Paste `*_API_KEY` on `90 系统文件/自动化/自进化钥匙.md`. The writer locks the flagship model. **No key:** already-logged-in Claudian-class CLI (`grok` / official Codex / `claude` / …). Distill and two-step promotion both run. Do not use a PATH-level `agent`.
3. Timer is on. Cloud chat automations are not this writer.
4. Write L1 logs and L2 distillation. When the five gates pass, write `provisional` the same day (no ask). Do not auto-promote to `active`.
5. Do not edit `canonical_sources.psv`.
6. On failure, leave a to-summarize note.
7. Uninstalling a Cursor / Codex / Claude Code / DSH mount does not stop this job. Disable the OS schedule yourself, then set `lamp: unused`.

Paste a live `*_API_KEY` on the vault page, **or** log in a coding CLI. Either lane distills **and** promotes. API lane auto-locks the flagship. Subscription lane is the Claudian channel (spawn the logged-in harness).
