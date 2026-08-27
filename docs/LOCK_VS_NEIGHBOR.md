# Lock vs neighbor

This is the reproducible experiment for the retrieval lock. It is **not** LongMemEval, LoCoMo, or a general memory-quality score.

**N=22** on a public fixture vault: hit 10, supersede 4, neighbor 4, negative 4. The author’s 25/25 is a different number (filled alias table on a private vault). Do not mix them.

Two claims. Do not merge them.

## Claim A — metadata (closed)

Naive cosine, given the expired page, returns it (supersede 0/4 old-page 4/4). After the same `invalid_at` filter — and, in `tfidf_map`, the live alias table with nouns prepended — cosine hits the live page (supersede 4/4). **Expired pages disappear because the filter and the map were applied, not because any ranker is smarter.** TF-IDF, lexical, and hybrid all tie the lock on that slice once they see the same information.

## Claim B — refusal (stands against an unthresholded baseline; a floor sweep does not tie the lock here)

After that ablation, **unthresholded** `tfidf_map` still cannot miss: on **4 negatives** it returns a live mapped page 4/4. The lock misses 4/4. That comparison is against a baseline that was **not given a refuse option**. It does **not** prove cosine cannot refuse.

The next row is a similarity floor on the same live map: miss if cosine(top-1) < `min_score`. Sweep:

```text
min_score   hit   negMiss   falseN   matches_lock
     0.00   100%      0%      23%   False
     0.05   100%      0%      23%   False
     0.08    90%      0%      23%   False
     0.19    90%     75%       9%   False
     0.20    90%    100%       5%   False
     0.23    90%    100%       0%   False
```

`matches_lock` means hit 10/10 **and** negative 4/4 miss **and** false_neighbor 0. **No floor on this fixture matches the lock.** The CJK gold hit `封账` scores ~0.06; the strongest negative scores ~0.19. Any floor that refuses all four negatives also drops that true hit. Closest refuse-and-zero-false-neighbor point: `min_score=0.23` → negatives 4/4 miss, false_neighbor 0, hit 9/10.

N=22, **4 negatives**. The 23% false-neighbor figure is 5/22, driven mostly by those 4 items. State the 4 when you quote it.

Recorded 2026-08-27, `python3 tests/fixtures/lock_vs_neighbor/run.py`:

| system | exact | false_neighbor | old_page | miss |
|---|---|---|---|---|
| krouter | 95.45% | **0** | **0** | 27.27% |
| tfidf (naive, expired pages in) | 36.36% | 59.09% | 18.18% | 4.55% |
| tfidf_map (same live map, no floor) | 77.27% | 22.73% | 0 | 0 |

The 22.73% is 5/22. Four of those five are the negatives. A floor of 0.23 zeros false_neighbor and refuses all 4 negatives, and drops hit to 9/10.

Dense retrieval (sentence-transformers, Mem0) is still untested.

## What runs

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

| System | What it sees | Refuse option? |
|---|---|---|
| krouter | Alias table + `invalid_at` | Yes (no hit → miss) |
| lexical / tfidf / hybrid | Every file, including expired | No (except lexical empty-token miss) |
| `*_live` | Same `invalid_at` filter; unmapped live pages stay | No |
| `tfidf_map` | Live alias rows; aliases in the document text | Not until the threshold sweep |

## What would falsify this

- Claim A: naive tfidf supersede `old_page` == 0, or ablated systems fail supersede after the filter
- Claim B: `threshold_any_matches_lock` is true on this gold file — then a cosine floor ties the lock here
- A dense encoder on the **same** gold file matching the lock on hit 10/10 and negative 4/4 miss
