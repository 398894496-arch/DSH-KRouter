# Lock vs neighbor

This is the reproducible experiment for the retrieval lock. It is **not** LongMemEval, LoCoMo, or a general memory-quality score.

**N=36** on a public fixture vault: hit 16 (9 lexical + 6 CJK rewrite + 1 English paraphrase), supersede 4, neighbor 4, negative 12. The author’s 25/25 is a different number (filled alias table on a private vault). Do not mix them.

Two claims. Do not merge them.

## Claim A — metadata (closed)

Naive cosine, given the expired page, returns it (supersede 0/4 old-page 4/4). After the same `invalid_at` filter — and, in `tfidf_map`, the live alias table with nouns prepended — cosine hits the live page (supersede 4/4). **Expired pages disappear because the filter and the map were applied, not because any ranker is smarter.** TF-IDF, lexical, and hybrid all tie the lock on that slice once they see the same information.

## Claim B — refusal (lexical TF-IDF on this fixture; not similarity retrieval in general)

After that ablation, **unthresholded** `tfidf_map` still cannot miss: on **12 negatives** it returns a live mapped page 12/12. The lock misses 12/12. That comparison is against a baseline that was **not given a refuse option**. It does **not** prove cosine cannot refuse.

The next row is a **word + character-trigram TF-IDF** floor on the same live map: miss if cosine(top-1) < `min_score`. Sweep:

```text
min_score   hit   negMiss   falseN   matches_lock
     0.00   100%      0%      36%   False
     0.05   100%      0%      36%   False
     0.08    75%      8%      33%   False
     0.19    62%    100%       3%   False
     0.23    62%    100%       0%   False
```

`matches_lock` means every hit exact **and** every negative a miss **and** false_neighbor 0. **No lexical TF-IDF floor on this fixture matches the lock.** That is not a claim that no similarity floor can.

The hinge is no longer one pair. Six CJK rewrite hits, each on a different live page, sit below the strongest of 12 English OOD negatives:

| id | query | score | page |
|---|---|---|---|
| H12 | 剪藏 | 0.057 | 用户偏好与工作约束 |
| H05 | 封账 | 0.058 | Seal the day from the log file |
| H15 | 发版 | 0.059 | Ship from main only |
| H16 | 纠错 | 0.077 | 纠错与取代记录 |
| H11 | 首页 | 0.093 | Agent第二大脑 |
| H14 | 定时器响了 | 0.106 | A timer that fired is not a product |

Strongest negative: `what is the weather in oslo` **0.188** against the English seal page. Same-page *lexical* aliases stay high (`sealed` ~0.26, `seal the day` ~0.44). The English paraphrase `close the books` scores **0.23** and does **not** invert — this gap is cross-script wording, not “every rewrite.”

Leave-one-out: drop **any one** rewrite hit, still no matching floor. Drop **any one** negative, still no matching floor. Word-only TF-IDF (no character trigrams) also finds no floor (7/7 rewrite invert).

This inversion is a known lexical-overlap failure on a bilingual alias map. A dense encoder could raise the CJK hits and open a gap. Until that row exists, the finding stays: **lexical TF-IDF on this gold file**. Not “thresholded retrieval.” Not “cosine.”

N=36, **12 negatives**, **6 inverted rewrite hits**. Holds on **this fixture**. Does not hold as a class-wide result.

Recorded 2026-08-27, `python3 tests/fixtures/lock_vs_neighbor/run.py`:

| system | exact | false_neighbor | old_page | miss |
|---|---|---|---|---|
| krouter | 97.22% | **0** | **0** | 38.89% |
| tfidf (naive, expired pages in) | 22.22% | 61.11% | 11.11% | 16.67% |
| tfidf_map (same live map, no floor) | 63.89% | 36.11% | 0 | 0 |

A floor of 0.23 zeros false_neighbor and refuses all 12 negatives, and drops hit to 62% (the CJK rewrite slice is gone).

**Dense retrieval is the next experiment, not a polish row.** If an embedding on the same gold file puts the six CJK hits above the strongest negative, a separating threshold may exist and Claim B does not generalize past lexical overlap. If the inversion remains, the finding can widen. Untested today (sentence-transformers, Mem0, or any dense encoder).

Word-stopped TF-IDF makes these 12 OOD queries score 0 here because the 7-page vault does not contain `oslo` / `kubernetes` / `guitar`. That is empty overlap on a tiny corpus, not a refuse policy. Do not cite it as cosine learning to miss.

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
- Claim B (lexical, this fixture): `threshold_any_matches_lock` is true, or `drop_any_one_rewrite_still_no_threshold` is false — then the no-floor line was one item
- Wider than lexical: a dense encoder on the **same** gold file finds a floor with every hit exact and every negative a miss. That would mean the inversion was TF-IDF’s wording gap, not a general refuse failure. Until that row is measured, do not say “similarity retrieval.”
