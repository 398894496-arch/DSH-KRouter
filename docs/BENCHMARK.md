# Memory honesty bench

Does an agent memory cite the right page, follow a correction, and refuse what it does not hold? Retrieval benches
usually score how often the right page shows up. This one scores the opposite failure, the one users actually get
burned by: a confident answer from the wrong page.

Everything is in [`bench/memory_honesty/`](../bench/memory_honesty/): a 30-page vault of plain Markdown, 30
questions, a runner, and a scorer that grades any system's output.

## The questions

| Kind | n | What the vault holds | Right behaviour |
|---|---|---|---|
| `correction` | 10 | an old page (`status: superseded`) and the newer page that replaces it, which also says so in its text | cite the new page first |
| `current` | 10 | one page that answers it | cite that page first |
| `refuse` | 10 | nothing that answers it, but a page that answers a *neighbouring* question: the search API timeout when the vault has the payments API timeout; file storage backups when it has database backups | refuse; citing the neighbour is a wrong citation |

## Metrics

- **Wrong-citation rate**: of the questions a system answered, the share whose first citation is not the gold page.
  Every answered `refuse` question counts as wrong.
- **Refusal**: `refuse` questions refused, of 10.
- **Correction hit**: `correction` questions whose first citation is the new page, of 10.
- **Current hit**: `current` questions whose first citation is the gold page, of 10.

## Results

Four systems, both question sets, run on 2026-10-12. Held-out means the 25 questions in `heldout.jsonl` that KRouter was
never tuned on ([`HELDOUT.md`](../bench/memory_honesty/HELDOUT.md)); dev means the 30 bench questions, on which KRouter
was fixed once (see below). Each cell gives the wrong-citation rate, refusals out of 10 neighbour questions, and right
answers on correction and current questions.

| System | Held-out: wrong citations | refused | corrections | current | Dev: wrong citations | refused | corrections | current |
|---|---|---|---|---|---|---|---|---|
| Plain full-text search (SQLite FTS5 BM25), always answers | 61% (14 / 23) | 1 / 10 | 4 / 9 | 5 / 6 | 63% (19 / 30) | 0 / 10 | 1 / 10 | 10 / 10 |
| basic-memory 0.22.1, default search (vector) | 60% (15 / 25) | 0 / 10 | 4 / 9 | 6 / 6 | 39% (11 / 28) | 2 / 10 | 7 / 10 | 10 / 10 |
| claude-mem 13.35.0, its search over what it observed | 60% (15 / 25) | 0 / 10 | 5 / 9 | 5 / 6 | 43% (13 / 30) | 0 / 10 | 7 / 10 | 10 / 10 |
| **KRouter 1.0.1** | **25% (3 / 12)** | **8 / 10** | 5 / 9 | 4 / 6 | 0% (0 / 17) | 10 / 10 | 8 / 10 | 9 / 10 |

What the table says, plainly:
- **Neighbour questions are where the systems differ.** The other three answer nearly every question that sounds like
  something in the vault, so a question about the search API timeout gets the payments API timeout page. KRouter
  refuses 8 of 10 on held-out.
- **KRouter pays for that in answerable questions.** On held-out it answered 9 of 15 answerable questions right;
  basic-memory answered 10 of 15, and claude-mem 10 of 15. Five of KRouter's six misses there are refusals of questions
  the vault does answer, when the question uses a word the page does not (lexical recall cannot bridge that); one is a
  wrong citation. Embedding
  search bridges it, and the same property is what makes it answer the neighbour questions.
- **Corrections are hard for everyone.** All four put the replaced page first on some correction questions. KRouter
  and claude-mem got 5 of 9 on held-out, basic-memory 4 of 9.

How each system was run (adapters in [`bench/memory_honesty/adapters/`](../bench/memory_honesty/adapters/), each
system's defaults, isolated HOME):
- **basic-memory 0.22.1** indexes the vault folder as a project (`basic-memory reindex`, 30 notes embedded) and
  answers with `basic-memory tool search-notes`. Its `--hybrid` and `--vector` modes gave identical results to the
  default. It refuses only when the search returns nothing.
- **claude-mem 13.35.0** (Claude Code plugin from its marketplace, observer `claude-haiku-4-5`) does not index a
  folder; it remembers sessions. It learned the vault the way it learns a user's docs: one Claude Code session read
  all 30 pages, one Read per page, and claude-mem recorded 30 observations (10 decision, 8 change, 12 discovery). Each
  question goes to its own search (`/api/search`, what its MCP search tool calls); results map to pages through each
  observation's `files_read`. It has no refusal: it always returned something. Running it isolated takes one extra
  setting: even with its own HOME, claude-mem looks for Claude Code's login in the macOS keychain, which is shared
  across HOMEs; `CLAUDE_MEM_CLAUDE_CONFIG_DIR` set to a fresh folder keeps it off your real login, and the worker then
  needs `CLAUDE_CODE_OAUTH_TOKEN` in its own environment.
- **KRouter** runs in-process (`run.py`); BM25 is `run.py --adapter bm25`.

Raw per-question output on the dev set, for every system, is in
[`bench/memory_honesty/results/2026-10-12/`](../bench/memory_honesty/results/2026-10-12/); grade any of them with
`run.py --answers`. Per-question held-out output is not published, to keep the held-out set usable (HELDOUT.md rule 3);
only the aggregates above are.

Not run: Obsidian Smart Connections (it runs inside the Obsidian app, with no headless search to call) and Mem0 (it
needs an LLM and a vector store configured, and has no default to compare against). Adapters are welcome.

### History on the dev set

| System | Wrong-citation rate | Refused | Correction hit | Current hit |
|---|---|---|---|---|
| KRouter 0.12.1 (first run, before any change) | 22% (4 / 18) | 7 / 10 | 5 / 10 | 9 / 10 |
| KRouter 0.13.0 to 1.0.1 | 0% (0 / 17) | 10 / 10 | 8 / 10 | 9 / 10 |

**Held-out, on questions KRouter was never tuned on.** An outside reviewer wrote 25 new questions for the same 30-page vault: 15 answerable ones phrased differently, and 10 neighbour questions. They were written independently of any tuning. KRouter 1.0: 25% wrong citations (3 / 12), 8 / 10 neighbours refused, 9 / 15 answerable right. Plain BM25 that always answers: 61%, 1 / 10. The questions are in [`bench/memory_honesty/heldout.jsonl`](../bench/memory_honesty/heldout.jsonl), frozen at 1.0.1; the rules for using them (aggregates only, no tuning toward them, what burns the set) and a log of who has seen what are in [`bench/memory_honesty/HELDOUT.md`](../bench/memory_honesty/HELDOUT.md). CI pins the questions and the vault and checks only a sanity guard against plain full-text search, never a floor. Quote this figure, or the 0.12.1 row (22%), as KRouter's wrong-citation rate, not the 0% above. The three wrong citations: a git branch-name format question cited the date-format page (both say "format"); a release-tag naming question and a checkout-page load-budget question each cited a neighbouring page.

**Read the 0.13.0 row as a development-set number.** The bench was written for 0.13.0, and its first run found a bug:
English function words (`what`, `which`, `does`, `should`) were counted as words "the vault has never seen", so a
plain English question about a page that was there got refused, while a neighbour question that happened to share
`what` and `do` with a page got answered. 0.13.0 drops those words from ranking and refusal and lets `services` match
`service`. The fix is general, not shaped to these 30 questions: on the author's Chinese vault the recall eval is
identical before and after. Still, KRouter was changed after seeing the bench, so the honest held-out figure is the
0.12.1 row.

The 0.13.0 misses are all refusals, never wrong answers. Each one asks with a word the page does not use: a pull
request "needs approvals" where the page says "merge"; an on-call "shift" where the page says "rotates"; "locally"
where the page says "local development". Lexical recall cannot bridge those. An embedding system would answer them,
and it would answer the neighbour questions too.

## Run it

```bash
python3 bench/memory_honesty/run.py                  # KRouter, in-process
python3 bench/memory_honesty/run.py --adapter bm25   # the plain full-text baseline
python3 bench/memory_honesty/run.py --answers mine.jsonl
python3 bench/memory_honesty/run.py --set heldout     # held-out set: aggregates only (HELDOUT.md)
```

To grade another system, index `bench/memory_honesty/vault/` with it, ask each question in
`bench/memory_honesty/questions.jsonl` (`q`), and write one JSON line per question:

```json
{"id": "C-release", "cited": ["Engineering/Release process.md"], "refused": false}
```

`cited` is in rank order and uses vault-relative paths. A system that returns chunks maps each chunk to its file.
`refused: true` means it said it had nothing; an empty `cited` with `refused: false` counts as a refusal too. CI runs
the KRouter row on every push (`tests/test_memory_honesty.py`), and its floors only go up.
