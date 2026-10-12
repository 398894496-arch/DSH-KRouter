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

| System | Wrong-citation rate | Refused | Correction hit | Current hit |
|---|---|---|---|---|
| Plain full-text search (SQLite FTS5 BM25), always answers | 63% (19 / 30) | 0 / 10 | 1 / 10 | 10 / 10 |
| KRouter 0.12.1 (first run, before any change) | 22% (4 / 18) | 7 / 10 | 5 / 10 | 9 / 10 |
| KRouter 0.13.0 | 0% (0 / 17) | 10 / 10 | 8 / 10 | 9 / 10 |

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

Not run yet: claude-mem, basic-memory, Obsidian Smart Connections, Mem0. Their adapters are welcome (see below); a
comparison will be published only with every system's raw output alongside it.

## Run it

```bash
python3 bench/memory_honesty/run.py                  # KRouter, in-process
python3 bench/memory_honesty/run.py --adapter bm25   # the plain full-text baseline
python3 bench/memory_honesty/run.py --answers mine.jsonl
```

To grade another system, index `bench/memory_honesty/vault/` with it, ask each question in
`bench/memory_honesty/questions.jsonl` (`q`), and write one JSON line per question:

```json
{"id": "C-release", "cited": ["Engineering/Release process.md"], "refused": false}
```

`cited` is in rank order and uses vault-relative paths. A system that returns chunks maps each chunk to its file.
`refused: true` means it said it had nothing; an empty `cited` with `refused: false` counts as a refusal too. CI runs
the KRouter row on every push (`tests/test_memory_honesty.py`), and its floors only go up.
