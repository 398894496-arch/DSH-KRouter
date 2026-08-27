# What a stranger can verify

This clone does **not** contain the author’s vault. The 25 LLM sessions, 72 sealed days, and 30 real tasks were measured there. They cannot be replayed from GitHub.

What *can* be replayed is the same **contract**, on files that ship in this repository.

## 1. Neighbor lock (already public)

Expired page vs refuse. Two claims. **N=36**.

```bash
python3 tests/fixtures/lock_vs_neighbor/run.py
python3 -m pytest -q tests/test_lock_vs_neighbor.py
```

Protocol: [`LOCK_VS_NEIGHBOR.md`](LOCK_VS_NEIGHBOR.md). Gold: [`tests/fixtures/lock_vs_neighbor/`](../tests/fixtures/lock_vs_neighbor/).

## 2. Filled-table analogue (this page)

The author’s mechanical pass is “every topic’s aliases unique-hit a live page.” The public analogue uses **this repo’s `template/`** and a 25-row map that does not contain private projects.

```bash
python3 tests/fixtures/clone_25/run.py
python3 scripts/verify_canonical_map.py
python3 -m pytest -q tests/test_clone_25.py
```

Recorded on this clone:

| Check | Result |
|---|---|
| Mechanical topics / aliases | **25/25** topics, **39/39** aliases, 0 conflicts |
| Rewrite paraphrases miss | **25/25** (the question is not an alias) |
| Listed short noun hits gold path | **25/25** |

This is **not** five fresh LLM sessions. The author’s 2026-08-21 rewrite set asked paraphrases a model had to compress into a noun. CI cannot be that model. The analogue pins the two halves a stranger can score without a private vault:

1. The paraphrase must **miss** (gate: do not dump the whole question as AND).
2. The noun written next to it must **hit** the gold page.

Map and questions: [`tests/fixtures/clone_25/`](../tests/fixtures/clone_25/). Vault under test is [`template/`](../template/), not the author’s notes.

Anyone with their own vault can point the same checker at it:

```bash
python3 scripts/verify_canonical_map.py \
  --map /path/to/canonical_sources.psv \
  --vault /path/to/YourVault
```

That reproduces the *method* of 26/26 · N/N. It does not publish the author’s map.

## 3. What stays a self-report

| Claim | Why it is not in this clone |
|---|---|
| Author LLM 25/25 (2026-08-21) | Questions name private projects. Scoring needed five new chat sessions. |
| 26/26 topics, 156/156 aliases on the live map | The live `canonical_sources.psv` is private. Run the checker at home; do not paste the map here. |
| 72 consecutive sealed days | Needs `05 时间日志/` for that window. Template ships one sample day. |
| 30 real tasks | Task logs are private. |

If those numbers are cited, they must stay labeled **self-report / not in this clone**.
