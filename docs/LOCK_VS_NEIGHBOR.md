# Lock vs neighbor

This is the reproducible experiment for the retrieval lock. It is **not** LongMemEval, LoCoMo, or a general memory-quality score. Those measure conversational fact recall with nearest-neighbor retrieval. This measures a different contract:

**Citing a neighbor is a failure. After a correction, the next call must hit the live page. A miss is success when there is no gold page.**

The author’s 25/25 blind test is not this experiment. That number proves the lock opens on a filled alias table. This fixture proves the lock refuses a plausible wrong page.

## What runs

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

No GPU. No extra pip. No network. The vault is `tests/fixtures/lock_vs_neighbor/vault/`, not the author’s notes and not `template/`.

Four retrievers, same gold file:

| System | Hit rule | Can miss? |
|---|---|---|
| krouter | Alias table. Expired map rows dropped. Dual-SHA receipt is out of scope here; path match is the score. | Yes |
| lexical | Count of query tokens in each markdown file | Yes, if no file contains a token |
| tfidf | Word + character-trigram TF-IDF cosine | Almost never; top-1 by cosine |
| hybrid | Reciprocal rank fusion of lexical and tfidf | Almost never |

`tfidf` is a vector nearest-neighbor baseline you can reproduce in CI. It is **not** a neural embedding. If you want an extra row, install `sentence-transformers` yourself and fork the runner; that row is not what CI claims.

## Slices

| Slice | Gold | What a vector system typically does |
|---|---|---|
| hit | Canonical path; the query carries an alias | Often right, sometimes a neighbor |
| supersede | Live page after `invalid_at`; the old page is still on disk and longer | Returns the old page |
| neighbor | Live constraint, or `null`; a trap page shares wording | Returns the trap |
| negative | `null` | Returns some file anyway |

Scoring is exact path equality. `false_neighbor` means the system returned a path that is not gold. `old_page` is the superseded deploy note.

## What would falsify this

- krouter `false_neighbor` > 0 on this gold file
- krouter `slices.supersede.old_page` > 0
- tfidf (or lexical) `slices.supersede.old_page` == 0 *and* krouter no longer unique on that slice — then the fixture is too weak, not a win
- a neural encoder, run on the **same gold file**, matching krouter on `false_neighbor` and `old_page`

A loss on `hit` paraphrases that are **not** in the alias table is expected. Coverage is the table. Do not cite that as a failure of the lock, and do not cite a win on `hit` as beating memory research.

## Measured on this fixture

Recorded 2026-08-27, `python3 tests/fixtures/lock_vs_neighbor/run.py`:

| system | exact | false_neighbor | old_page | miss |
|---|---|---|---|---|
| krouter | 0.9545 | **0** | **0** | 0.2727 |
| lexical | 0.4091 | 0.50 | 0.1818 | 0.1818 |
| tfidf | 0.3636 | 0.5909 | 0.1818 | 0.0455 |
| hybrid | 0.3636 | 0.5909 | 0.1818 | 0.0455 |

Supersede slice: krouter 4/4 live page; lexical/tfidf/hybrid 4/4 old page.

That is the claim this repository can stand on: **in the class of retrieval where a neighbor cite is a protocol violation, a missy alias lock beats cosine-over-files on this public fixture.** It is not a claim that vector memory is useless, or that clone coverage equals a filled second brain.
