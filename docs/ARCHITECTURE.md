# KRouter Obsidian architecture

This is the protocol detail. README is the entry; [`PROTOCOL.md`](../PROTOCOL.md) is the invariant list. The author’s private notes are not in this repository.

**Product (do not skip):** self-evolution (seal → distill) → two-step promotion (auto `provisional` the same day when five gates pass; `active` only after ask + adopt + accepted task) → correction-first → retrieval as the lock. Timer is on by default. The key is your vault-page `*_API_KEY` or an already-logged-in local CLI. `lamp: unused` = you turned the timer off. Author-vault scores below are not clone scores and cannot be reproduced from this clone.

KRouter splits knowledge into **four write-up maturity layers** and **five spatial zones**. Layers answer how far this claim can be trusted. Zones answer where the file lives. Agents must read the vault through layer 4. Chat memory and vector indexes are not a second source of truth.

**What this clone can prove** is three layers, do not merge. Full split: [`VERIFY.md`](VERIFY.md). (1) Implementation: `clone_25` — the lock does what this page says. (2) Comparison: [`LOCK_VS_NEIGHBOR.md`](LOCK_VS_NEIGHBOR.md) — after the same metadata, refuse vs unthresholded lexical TF-IDF and multilingual MiniLM. (3) Field self-report below: not in this repository.

Vault folder names stay in Chinese. That is the on-disk layout.

```mermaid
flowchart TB
  subgraph write ["Write-up maturity"]
    L1["L1 Full logs<br/>05 时间日志"]
    L2["L2 Distillation<br/>daily evolution / 04 reviews"]
    L3["L3 Promotion<br/>auto provisional → ask → active"]
    L1 --> L2 --> L3
  end
  L4["L4 Retrieval<br/>short noun + alias table + SHA receipt"]
  L3 --> L4
  L1 -.-> L4
  L2 -.-> L4
```

Dashed lines: retrieval may land on any layer. **Action may cite only a formal method, a current correction, or the receipt’s `canonical_source`.** Layers 1 and 2 are clues by default, not action basis.

## Five spatial zones

These exist alongside the four layers. They do not replace them.

| Zone | Duty | Maturity |
|---|---|---|
| `01 项目` | Work in progress, open scope, project evidence | Process. Does not promote to method |
| `02 经验与方法` | What to do next time | L3. Includes `准经验/` |
| `03 资料与证据` | Inputs, originals, result evidence | Source layer. Summaries never replace originals |
| `04 已完成与复盘` | Finished results and reviews | One L2 landing |
| `05 时间日志` | What happened that day | L1 |
| `90 系统文件` | Protocol, indexes, correction ledger, validation, automation health | Governance. Not a fifth business zone |

The only home page is `Agent第二大脑.md`. Do not add a parallel dashboard, workbench, or second entrance.

---

## L1 Full logs

Path: `05 时间日志/YYYY-MM/DD｜one-line summary.md`.

1. **One sealed note per day.** A missing day must leave a “to-summarize” (or equivalent) gap. Empty files do not count as a seal.
2. **Episodic memory is not result memory.** A log proves something was done, asked, or failed. It does not prove the project was accepted.
3. **Do not store full chats, hidden reasoning, or credentials.** Trace with `source_ref` to an index or evidence page.
4. **The filename must show what the day was for.** `DD｜one-line summary`. Do not replace the actual work with abstract knowledge-management jargon.
5. **Logs may be accepted by a host-designated agent** (for example `agent-accepted`). This does **not** cover formal `02` methods.

Raw evidence (`03`, Clippings originals) sits beside L1. Originals are not replaced by logs or summaries. Copy Clippings into a formal location; do not move, edit, or delete the originals.

---

## L2 Distillation

L2 pulls a compact, project-usable clue out of L1. It is not a second original.

Landings:

- Daily evolution (project roll-up, same-day method candidates, monthly index)
- `04 已完成与复盘`
- Derived notes with `source_ref`, `verified_at`, and scope

1. **Derived notes keep source, time, scope, trust, and limits.**
2. **Two lanes, same job.** API key first: lock the provider's flagship model and run distill + two-step promotion. No key: spawn a logged-in Claudian-class CLI (`grok`, official Codex, `claude`, …) with vault cwd — **subscription unattended**, not Grok-only. Grok `--permission-mode bypassPermissions` (not `acceptEdits`); Claude `--dangerously-skip-permissions`; Codex `exec --sandbox workspace-write`. The timer pins this repo's `krouter-obsidian`, never a live `obsidian-knowledge-router`. Do not use a PATH-level `agent`. Chat/IDE login is not a spawnable harness. Mounted agents run `status` and tell the host if `host_action` is present. An in-vault chat plugin is not the writer. On failure, leave a to-summarize note. Do not switch shells and rewrite.
3. **One product: DSH-KRouter.** The writer lives in `extras/host-daily-evolution/`. `extras/dsh` is the DSH socket on the same `OBSIDIAN_VAULT`. Not two repositories, not a side plugin. Uninstalling the DSH socket does not delete notes and does not stop the timer.
4. Distillation may propose candidates. **It must not write formal `02`.**

---

## L3 Promotion

`02` answers only “what should we do next time.” Methods come from real project results, with conditions and limits. Process stays in `01`.

### Status

| status | Meaning | Agent use |
|---|---|---|
| `candidate` | Still in a project or materials | Must not pose as a method or result |
| `provisional` | Quasi-method / quasi-correction | Draft you may use. On the next similar task, ask whether to adopt |
| `active` | Formal method or formal correction | Action basis, still check expiry |
| `rejected` / `superseded` | Rejected or replaced | Not current rule |

When machine content hits a real task, has a clear source, a verifiable result, is de-duplicated, and states its limits: **write provisional the same day.** Do not leave it as an orphan candidate. Do not treat it as a formal method.

### Five gates into provisional (same day)

All five required for `status: provisional`:

1. Comes from a real project or problem.
2. Has a result, evidence, or a same-day correction.
3. De-duplicated against existing methods.
4. States conditions and limits.
5. Lowers judgment or execution cost next time.

Fail any one: keep it in `01` / `03` as a candidate, or mark the gap. Do not promote.

### Promote to formal

```text
provisional  --next similar task-->  matcher asks whether to adopt
                                    ├ host adopts AND this task is accepted → active
                                    └ rejected or not accepted → stay provisional, or rejected
```

The matcher is `skill/krouter-obsidian/scripts/ask_product.py`. At most one page. `record` does not write `active`; `promote` does, after adopt + this task accepted. This clone ships the matcher, not an author’s trigger list.

Corrections follow the same ladder: quasi-correction → ask → adopt and accept → correction ledger `active`. The current user instruction and the latest `supersedes` beat old logs.

An in-vault chat plugin does not own architecture and does not block promotion. Whoever finishes the work writes it. One file has one writer at a time.

### Optional: method → Skill

A formal method may become a Skill candidate only after **at least three** verified repeats of the same class of task. A Skill candidate is still not a formal `02` method. File counts, session counts, and export versions are not a substitute for verified repeats.

---

## L4 Retrieval

The agent does not dump a full question into the vault. It sends one contiguous short noun. No vector store. No retrieval subprocess.

### Routes

| Command | Use |
|---|---|
| `status` | Home frontmatter. A complete result needs no second lookup |
| `preference` | Host preferences and constraints |
| `correction` | Corrections and `supersedes` |
| `memory` | High-trust memory index |
| `project` | Literal search under `01 项目` |
| `search` | Alias hit first; otherwise vault-wide literal search |
| `suggest` | Nearest aliases on a miss. Hints only; not a hit |

The host sets `OBSIDIAN_VAULT`.

### Alias scoring

`canonical_lookup.py` against `canonical_sources.psv`:

1. Normalized alias equals query: highest.
2. Alias is a substring of the query: next.
3. Query is a substring of the alias and length ≥ 2: next.
4. Strip particles `的了着过地得` and punctuation before compare.
5. Tied scores resolve to the lowest id only when they point at the same file; otherwise no hit.
6. If the whole string misses, sum scores over whitespace tokens and use the same tie-break.

Hit: receipt `canonical_match: true`. The agent **must** open and cite `canonical_source`. Do not substitute the preferences note or another nearby page. If the mapped page is `candidate` or `rejected`, still read it.

Miss: literal `rg` in that route’s scope. Skip `Clippings/`, backups, and cold mirrors.

### Receipt

Every call emits `knowledge-route-v2`: time, route, hit status, source path, source SHA-256, map SHA-256. “I remember the vault had that” without a receipt is not retrieval.

### Trust (on read)

High reliability is not “mark everything high-trust.” The agent must always know four things: what may drive action, what is only a clue, what must be re-checked, and what has been denied.

| Grade | Condition | Use |
|---|---|---|
| High trust | Valid status; clear source; user confirm or direct file evidence; scope and time stated | Action basis; still check expiry |
| Medium trust | Historical backfill, partial evidence, not finally accepted | Retrieval clue only |
| Candidate / low trust | No source, news, Clippings, machine candidates, inference | Not a fact or result |

Five memory classes: `constraint` preferences and corrections; `result` project outcomes; `method` verified practice; `evidence` originals; `episodic` logs. Conflict order: current user instruction → correction ledger → current real files → project evidence → methods → historical logs → raw materials and machine content.

---

## Write-back

| Write | Location |
|---|---|
| Project action, status, unfinished work | `01 项目/` |
| Verified methods | `02 经验与方法/` (provisional, then formal) |
| Originals and evidence | `03 资料与证据/` |
| Finished results and reviews | `04 已完成与复盘/` |
| Daily events | `05 时间日志/` |
| Protocol, indexes, validation, health | `90 系统文件/` |

New semantic search, vector layers, graph databases, or auto-injection must first beat Markdown + this router + `rg`, and need explicit host authorization. Do not revive retired vector memory or graph hot paths by default.

---

## What has been run (three layers)

Do not merge. [`VERIFY.md`](VERIFY.md).

### 1. Implementation

`clone_25` on `template/`: exhaustive **25/25** topics, **39/39** aliases, 0 conflicts (table consistency, not a smart ranker). Rewrite: **25/25** paraphrases miss; **25/25** nouns hit. That is “the code matches the protocol,” not five LLM sessions. `template/` is a clean floor, not live-vault difficulty.

```bash
python3 tests/fixtures/clone_25/run.py
```

`verify_canonical_map.py` checks a host’s own map. It does **not** replay the author’s 26/26 · 156/156.

### 2. Comparison

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

**Claim A (closed):** naive cosine, given the expired page, returns it. After the same `invalid_at` filter, TF-IDF / lexical / hybrid tie the lock on the supersede slice. Expired pages disappear because the filter and the map were applied.

**Claim B (lexical TF-IDF on this fixture):** unthresholded `tfidf_map` still returns a page on every negative. The lock misses. A TF-IDF floor sweep, including leave-one-out on 6 CJK rewrite hits and 12 negatives, finds no operating point that matches the lock.

**Claim C (MiniLM, lightweight):** same floor sweep as Claim B. CJK inversion gone. Precision miss: unthresholded `H15` 发版 ranks the seal page. A floor cannot repair a wrong live page. Replay `dense_vectors.json` (frozen vectors, not a live encoder download).

**Claim D (BGE-M3, middleweight dense):** same floor sweep. Hit 16/16. Floor 0.40: 16/16 hits and 12/12 OOD negatives refuse; leftover is neighbor `B03` 生产事故 → timer page (not one of N01–N12). Floor 0.45: false-neighbor 0, a true hit drops. No operating point is 16/16 + 12/12 OOD refuse + false-neighbor 0. Replay `dense_m3_vectors.json`. On this contract the lock beats that stack; heavyweight hybrid + rerank is out of scope.

Full protocol: [`LOCK_VS_NEIGHBOR.md`](LOCK_VS_NEIGHBOR.md). Fixture: [`tests/fixtures/lock_vs_neighbor/`](../tests/fixtures/lock_vs_neighbor/).

### 3. Field self-report (not in this clone)

These numbers are from the author’s private vault. **This repository does not contain the materials to reproduce them.** They are a self-report, not a receipt. To measure *your* table, run `verify_canonical_map.py` on *your* files. To count *your* sealed days, run `verify_sealed_days.py` on *your* `05 时间日志/`. Neither replays the author’s 26/26 or 72 days.

Home page `verified_at: 2026-08-21`.

| Result | Detail |
|---|---|
| Retrieval blind test | 25/25: correct answers and the specified canonical source |
| Canonical routing | 26/26 topics, 156/156 aliases, map files all present |
| Consecutive seals | 72 days (2026-06-10 → 2026-08-20) |
| Real tasks | 30, covering actual work in that window |
| Execution gate | Passed. Pre-action recall in effect; Clippings mutate/move/delete and Obsidian restart are hard-blocked |
| Host daily evolution | Running. Writer is a pinned local CLI |

**Retrieval:** one short noun, one page, dual SHA receipt. The agent must cite `canonical_source`. Experience is retrieved. The 25/25 row above is layer 3 (self-report). Layer 1 is [`VERIFY.md`](VERIFY.md). Layer 2 is [`LOCK_VS_NEIGHBOR.md`](LOCK_VS_NEIGHBOR.md).

**Corrections:** written to canonical pages (`supersedes` / quasi-correction → formal correction). The next similar task hits the new page through L4. Old wording is not current rule. Provisional methods become `active` after adopt + accept. The vault gets sharper; the agent gets steadier.

The writer is the product (`extras/host-daily-evolution/`). The execution hook is optional. The DSH plugin (`extras/dsh`) is a mount on the same vault, not a second knowledge base. The author’s vault already runs daily evolution under this protocol.

Chinese overview: [`README.zh.md`](../README.zh.md).
