# Lock vs neighbor

This is the reproducible experiment for the retrieval lock. It is **not** LongMemEval, LoCoMo, or a general memory-quality score.

**N=36** on a public fixture vault: hit 16 (9 lexical + 6 CJK rewrite + 1 English paraphrase), supersede 4, neighbor 4, negative 12. The author’s 25/25 is a different number (filled alias table on a private vault). Do not mix them.

Four claims. Do not merge them.

## Claim A — metadata (closed)

Naive cosine, given the expired page, returns it. After the same `invalid_at` filter — and, in `tfidf_map` / `dense_map`, the live alias table with nouns prepended — cosine hits the live page (supersede 4/4). **Expired pages disappear because the filter and the map were applied, not because any ranker is smarter.**

Lexical / TF-IDF / hybrid: naive supersede old-page 4/4. Multilingual MiniLM: naive supersede old-page **3/4** (`S01` “how to deploy” already ranks the live page). After the filter, MiniLM is 4/4 live, same as the lock.

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

`matches_lock` means every hit exact **and** every negative a miss **and** false_neighbor 0. **No lexical TF-IDF floor on this fixture matches the lock.**

The hinge is six CJK rewrite hits, each on a different live page, sitting below the strongest of 12 English OOD negatives. Strongest negative: `what is the weather in oslo` **0.188**. Leave-one-out: drop any one rewrite or any one negative, still no matching floor.

This inversion is a known lexical-overlap failure on a bilingual alias map. That is Claim B. Claim C is the dense encoder on the same gold file.

## Claim C — dense retrieval (multilingual MiniLM on this fixture)

Encoder: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 256 tokens, L2-normalized. Pytest **replays** [`dense_vectors.json`](../tests/fixtures/lock_vs_neighbor/dense_vectors.json) (no extra pip, no network, no GPU). Recompute after gold or vault text changes:

```bash
HF_HUB_DISABLE_XET=1 python3 tests/fixtures/lock_vs_neighbor/encode_dense.py
```

(`requirements-dense.txt`. A fingerprint mismatch fails the run; do not edit the JSON by hand.)

Unthresholded `dense_map` still cannot miss: 12/12 OOD negatives (N01–N12) return a live mapped page. The lock misses 12/12.

The lexical CJK inversion is **gone**. Seven rewrite hits all score above the strongest OOD negative (`min_rewrite` 0.3179 > `max_neg` 0.2929, inverted 0). MiniLM is not TF-IDF. Keep that: this failure is **not** the lexical-overlap hinge.

This is a **precision** miss, not a floor miss. Unthresholded, `H15` 发版 already ranks the seal-the-day page, not deploy (score 0.3179). A floor can only drop a match; it cannot turn a wrong live page into the right one. So even when every OOD negative sits below the floor, one rewrite hit is still a false neighbor:

```text
min_score   hit   negMiss   falseN   matches_lock
     0.00    94%      0%      42%   False
     0.30    94%    100%       6%   False
     0.40    81%    100%       0%   False
```

Leave-one-out: drop any one rewrite or any one negative, still no matching floor — because `H15` is wrong **before** any threshold.

This is one multilingual MiniLM on this 36-item fixture. Lightweight. Do not fold this into Claim D. Claim D’s leftover is a different slice.

## Claim D — middleweight dense (BGE-M3 on this fixture)

Encoder: `BAAI/bge-m3`, CLS pooling, 512 tokens, L2-normalized, **dense vector only** (no sparse, no ColBERT, no reranker). Pytest replays [`dense_m3_vectors.json`](../tests/fixtures/lock_vs_neighbor/dense_m3_vectors.json). Recompute:

```bash
HF_HUB_DISABLE_XET=1 python3 tests/fixtures/lock_vs_neighbor/encode_dense.py --mid
```

Delete the Hub snapshot after encoding. It is not part of the clone.

Unthresholded `dense_m3_map` still cannot miss: 12/12 OOD negatives return a live mapped page. Hit slice is **16/16** — `H15` 发版 is correct here (MiniLM ranked the seal page). CJK inversion gone (`min_rewrite` 0.4146 > `max_neg` 0.3992).

This is a **near-miss on one neighbor item**, not “a floor did nothing.” Sweep:

```text
min_score   hit   negMiss   falseN   matches_lock
     0.00   100%      0%      36%   False
     0.40   100%    100%       3%   False
     0.45    94%    100%       0%   False
```

At 0.40: every alias hit stays (16/16) and every OOD negative (N01–N12) refuses (12/12). The leftover is **not** one of those 12. It is neighbor-slice `B03`: query「how to handle a production incident」(gold null) cites `A timer that fired is not a product.md`. False-neighbor on the fixture is 1/36 (~3%). At 0.45 that neighbor cite clears; a true hit drops. No operating point is 16/16 + 12/12 OOD refuse + false-neighbor 0.

Dropping `H15` opens a matching floor on the rest — the remaining gap is this one neighbor trap, not CJK inversion. Naive BGE-M3 supersede old-page 4/4; after the map, 4/4 live.

Heavyweight (hybrid + rerank) is out of scope: wrong weight class, not a debt. The mainstream opponent on this bout is middleweight dense (BGE-M3 + a floor). Not OpenAI embeddings.

## What runs

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

**How strangers verify.** `clone_25` and the lexical/TF-IDF rows: `python3` + `rg`, no download. MiniLM and BGE-M3: pytest replays fingerprint-checked JSON. That audits the recording. It does **not** mean a stranger re-downloads the encoder and gets new vectors. Optional re-encode: `encode_dense.py`. Hub snapshots are not in the clone.

| System | What it sees | Refuse option? |
|---|---|---|
| krouter | Alias table + `invalid_at` | Yes (no hit → miss) |
| lexical / tfidf / hybrid / dense | Every file, including expired | No (except lexical empty-token miss) |
| `*_live` | Same `invalid_at` filter; unmapped live pages stay | No |
| `tfidf_map` / `dense_map` / `dense_m3_map` | Live alias rows; aliases in the document text | Not until the threshold sweep |

## What would falsify this

- Claim A: naive tfidf supersede `old_page` == 0, or ablated systems fail supersede after the filter
- Claim B (lexical, this fixture): `threshold_any_matches_lock` is true, or `drop_any_one_rewrite_still_no_threshold` is false
- Claim C (MiniLM, this fixture): `dense_threshold_any_matches_lock` is true. Measured 2026-08-28: false because `H15` 发版 already ranks the seal page before any floor.
- Claim D (BGE-M3, this fixture): `dense_m3_threshold_any_matches_lock` is true (16/16 hits, 12/12 OOD negatives miss, false_neighbor 0). Measured 2026-08-28: false. At 0.40 the leftover is neighbor `B03` 生产事故 → timer page, not one of N01–N12.

Recorded 2026-08-28, `python3 tests/fixtures/lock_vs_neighbor/run.py`:

| system | exact | false_neighbor | old_page | miss |
|---|---|---|---|---|
| krouter | 97.22% | **0** | **0** | 38.89% |
| tfidf (naive) | 22.22% | 61.11% | 11.11% | 16.67% |
| tfidf_map | 63.89% | 36.11% | 0 | 0 |
| dense (naive MiniLM) | 41.67% | 58.33% | 8.33% | 0 |
| dense_map | 58.33% | 41.67% | 0 | 0 |
| dense_m3 (naive BGE-M3) | 41.67% | 58.33% | 11.11% | 0 |
| dense_m3_map | 63.89% | 36.11% | 0 | 0 |

Two encoders, two failures — do not merge them into “neither matched the lock.”

- **MiniLM (lightweight):** precision. Unthresholded, `H15` 发版 already cites the seal page. A floor cannot repair a wrong live page. CJK rewrite inversion is gone (that was Claim B).
- **BGE-M3 (middleweight):** near-miss. At 0.40: 16/16 hits and 12/12 OOD negatives refuse. Leftover is neighbor `B03` (生产事故 → timer). At 0.45: false-neighbor 0, one true hit drops.

The lock has a matching point; neither embedding stack does, for those different reasons. That is the “better than mainstream embedding RAG” claim on this contract (refuse when gold is null; never cite a neighbor). Unthresholded top-1 is the first row of each sweep. Heavyweight is not a postponed bout.
