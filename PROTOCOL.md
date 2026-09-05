# Protocol

This is an **Agent knowledge OS**, not a search plugin.

- **Self-evolution** is the product (seal → distill → two-step promotion). Timer is **on by default**. **API key first:** lock that provider's flagship model and run distill + promotion. **No key:** the user's own Claudian-class CLI subscription (`grok` / official Codex / `claude` / …) does the same work. `lamp: unused` = you turned the timer off.
- **Promotion is two-step:** five gates pass → write `provisional` the **same day**, no ask. Next similar task → **ask** (matcher in `skill/krouter-obsidian/scripts/ask_product.py`; at most one). Host adopts → `record`. This task accepted → `promote` writes `active`. Do not write `active` on `record`.
- **Correction-first:** current instruction and latest `supersedes` beat old logs.
- **Retrieval is the lock:** short noun, dual SHA-256 receipt, no vector store. A neighbor cite is a protocol violation.

Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

1. Five zones: `01 项目` in progress; `02 经验与方法` verified reusable methods; `03 资料与证据` inputs and evidence; `04 已完成与复盘` finished results; `05 时间日志` what happened that day.
2. Four maturity layers: full logs → distillation → promotion → retrieval. Formal `02` requires the two-step gates above. Candidates stay in projects or materials until the five gates pass.
3. On conflict: the current user instruction and the latest `supersedes` beat old logs.
4. Clippings originals are copied only. Do not move them.
5. Routing: match `canonical_sources.psv` with a short noun (exact > alias in query > query in alias; same score and same file → lowest id; otherwise no hit). Open that page. On a miss, print alias suggestions (hints only) and literal-search the route’s scope. Same-score miss across two files: print `host_prompt` and do not guess. Windows may run `route_knowledge.py` (same contract as the POSIX script). No vector store. Evidence is three layers — implementation, comparison, self-report: [`docs/VERIFY.md`](docs/VERIFY.md). Neighbor cite is a failure: [`docs/LOCK_VS_NEIGHBOR.md`](docs/LOCK_VS_NEIGHBOR.md).
6. Every route prints a receipt: time, source path, source SHA-256, map SHA-256.
7. Two lanes, same job (distill + two-step promotion). **API key first:** read `90 系统文件/自动化/自进化钥匙.md`, lock the provider's flagship model (`/models` catalog; skip mini/haiku), run `api_writer.py`. **No key:** spawn a logged-in Claudian-class CLI (`grok`, official Codex, `claude`, opencode, kimi, pi, vibe, antigravity) with that harness's flagship. Do not use a PATH-level `agent`. Chat/IDE login is not a spawnable harness. No extra env file. Mounted agents must run `status` and tell the host if `host_action` is present. Do not print secrets. Do not commit a live key.
8. **One product: DSH-KRouter.** Cursor, Codex, Claude Code, and DeepSeek Harness are sockets on one vault. Sharing is the vault and the alias map, not a second protocol. `extras/dsh` is the DSH socket (read-only tools). `extras/host-daily-evolution` is the writer. They are not two projects. Uninstalling the DSH socket does not delete notes. `dsh plugin add` does not start the timer.
