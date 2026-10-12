## What and why

## Evidence
<!-- A change to ranking, refusal or card checks needs before / after numbers on the same run:
     `python -m pytest -q tests/test_recall_bench.py` (English and Chinese template benches) and, if you have one,
     your own held-out questions. See CONTRIBUTING.md. -->

- [ ] `python -m pytest -q` passes
- [ ] Tests and evaluation runs did not write the host's query log (`KROUTER_NO_QUERY_LOG=1`)
- [ ] Did not look at held-out per-question results (`--reveal`) while making this change, and did not read or edit `bench/memory_honesty/heldout.jsonl` / `heldout2.jsonl.gz`, the bench vaults or their pins (`bench/memory_honesty/HELDOUT.md`)
- [ ] CHANGELOG.md updated
