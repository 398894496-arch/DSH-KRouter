# What a stranger can verify

Three layers. Do not merge them. They do not prove the same thing.

| Layer | What it proves | Reproducible from this clone? |
|---|---|---|
| 1. Implementation | The lock does what [`ARCHITECTURE.md`](ARCHITECTURE.md) says | Yes — `clone_25` |
| 2. Comparison | After the same metadata, the lock refuses where unthresholded lexical TF-IDF still cites | Yes — `lock_vs_neighbor` |
| 3. Field self-report | Author’s filled vault, one window | **No.** Labeled. Use the checker on *your* vault. |

This is **not** five fresh LLM sessions. 这不是五次新会话LLM盲测. The author’s 2026-08-21 rewrite set asked paraphrases a model had to compress into a noun. CI cannot be that model. `clone_25`’s 25/25 is not the same kind of evidence as that private 25/25.

`template/` is a clean minimum sample. Names are short, topics barely collide. It is a **floor** (the mechanism is not buggy), not a **ceiling** (it does not show the dirty live vault). Real notes are messier.

---

## Layer 1 — implementation (clone_25)

The map against [`template/`](../template/). Two different checks. Do not quote them as one score.

### Exhaustive map check

**25/25** topics, **39/39** aliases, **0** conflicts.

This is an enumeration, not a sample. Every alias is looked up; every pair is checked for collision. There is no “N is small” caveat. It proves **this table is internally consistent**. It does not prove the ranker is clever.

```bash
python3 scripts/verify_canonical_map.py
python3 tests/fixtures/clone_25/run.py
python3 -m pytest -q tests/test_clone_25.py
```

### Invariant check (rewrite)

**25/25** paraphrases miss. **25/25** listed short nouns hit the gold page.

That is **implementation correctness**: whole-sentence rewrite does not fire AND matching; a protocol noun finds the gold page. Code does what the protocol wrote. No bug on this sample.

It does **not** replace layer 2. Layer 2 asks whether that matching *choice* beats lexical cosine. Layer 1 asks whether the code implements the choice.

Map and questions: [`tests/fixtures/clone_25/`](../tests/fixtures/clone_25/).

### The checker vs the author’s 26/26 · 156/156

`verify_canonical_map.py` lets **any host** check **their** map against **their** vault.

```bash
python3 scripts/verify_canonical_map.py \
  --map /path/to/canonical_sources.psv \
  --vault /path/to/YourVault
```

It does **not** verify the historical claim “the author’s live map was 26/26 · 156/156.” That map is not in this repository. Running the script on `template/` is not a replay of that number.

---

## Layer 2 — comparison (lock vs neighbor)

Expired page vs refuse. Four claims. **N=36**. Protocol: [`LOCK_VS_NEIGHBOR.md`](LOCK_VS_NEIGHBOR.md).

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

- **Claim A (closed):** expired pages vanish because `invalid_at` and the map were applied, not because a ranker is smarter. MiniLM naive old-page is 3/4; after the same filter it is 4/4.
- **Claim B (lexical TF-IDF on that fixture):** after the same information, the lock refuses; unthresholded cosine still returns a page. Six CJK rewrites sit below the strongest OOD negative. A floor sweep, including leave-one-out, finds no operating point that matches the lock.
- **Claim C (multilingual MiniLM on that fixture):** same floor sweep as Claim B. CJK inversion is gone. Failure is precision: unthresholded, `H15` 发版 already ranks the seal page, not deploy. A floor cannot repair that. Replay: `dense_vectors.json` (not a live encoder). Lightweight.
- **Claim D (BGE-M3 on that fixture):** same floor sweep. Hit 16/16 including 发版. Floor 0.40: 16/16 hits and 12/12 OOD negatives (N01–N12) refuse; leftover is neighbor `B03`「生产事故」→ timer page — not one of those 12. Floor 0.45: false-neighbor 0, a true hit drops. No operating point is 16/16 + 12/12 OOD refuse + false-neighbor 0. Replay: `dense_m3_vectors.json`. Middleweight is the mainstream opponent. Heavyweight (hybrid + rerank) is out of scope.

Gold: [`tests/fixtures/lock_vs_neighbor/`](../tests/fixtures/lock_vs_neighbor/). Here N *is* small; say so when you quote false-neighbor rates.

`clone_25` and the lexical/TF-IDF rows replay with `python3` + `rg` from this clone. MiniLM and BGE-M3 rows replay frozen JSON (`dense_vectors.json`, `dense_m3_vectors.json`) plus a content fingerprint. That checks the recorded vectors, not a stranger re-downloading the encoder. Re-encode is optional (`encode_dense.py`); Hub snapshots are not in the clone.

---

## Layer 3 — field self-report (not in this clone)

Measured 2026-08-21 on the author’s private vault. **This repository does not contain the materials to reproduce them.** Treat as a self-report, not a receipt.

| Claim | Why it is not in this clone |
|---|---|
| LLM 25/25 (2026-08-21) | Questions name private projects. Scoring needed five new chat sessions. |
| 26/26 topics, 156/156 aliases | The live map is private. The checker on *your* files is a different measurement. |
| 72 consecutive sealed days | Needs that window’s `05 时间日志/`. Template ships one sample day. |
| 30 real tasks | Task logs are private. |

`verify_sealed_days.py` is the same trust model as `verify_canonical_map.py`: it measures **this vault**, it does **not** replay “the author sealed 72 days.”

A day is sealed when `05 时间日志/YYYY-MM/DD｜*.md` exists, is not empty, and is not a `待总结` / `to-summarize` stub. Empty files are gaps. Same-day stub + body counts as sealed. Omit `--from-date` / `--through-date` and the window is the first and last day files found.

```bash
python3 scripts/verify_sealed_days.py
python3 scripts/verify_sealed_days.py --vault /path/to/YourVault
python3 scripts/verify_sealed_days.py \
  --vault /path/to/YourVault \
  --from-date 2026-06-10 \
  --through-date 2026-08-20
python3 -m pytest -q tests/test_sealed_days.py
```

Titles stay local. The report prints dates and gap kinds only.
