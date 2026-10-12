"""The published comparison on the dev set (docs/BENCHMARK.md) is reproducible from the raw output stored in the repo.

basic-memory and claude-mem cannot run in CI (an index, a Claude Code plugin with a model behind it), so their raw
per-question answers from the 2026-10-12 run are stored; these tests grade them again and check the published rows.
KRouter and BM25 are re-run live, so a change to either shows up here as a changed row.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "bench/memory_honesty/results/2026-10-12"
spec = importlib.util.spec_from_file_location("mh_bench_cmp", REPO / "bench/memory_honesty/run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

PUBLISHED_DEV = {  # docs/BENCHMARK.md, dev columns
    "bm25": (19, 30, "0/10", "1/10", "10/10"),
    "basic-memory-0.22.1": (11, 28, "2/10", "7/10", "10/10"),
    "claude-mem-13.35.0": (13, 30, "0/10", "7/10", "10/10"),
    "krouter-1.0.1": (0, 17, "10/10", "8/10", "9/10"),
}


def _row(res: dict) -> tuple:
    return (res["wrong_citations"], res["answered"], res["refused"], res["correction_hit"], res["current_hit"])


def test_stored_raw_output_reproduces_the_published_dev_rows():
    rows = bench.questions("dev")
    for name, want in PUBLISHED_DEV.items():
        answers = [json.loads(x) for x in (RESULTS / f"{name}.dev.jsonl").read_text(encoding="utf-8").splitlines() if x]
        assert [a["id"] for a in answers] == [r["id"] for r in rows], name
        assert _row(bench.score(rows, answers)) == want, name


def test_live_krouter_and_bm25_still_match_the_published_rows():
    rows = bench.questions("dev")
    assert _row(bench.score(rows, bench.krouter_answers(rows))) == PUBLISHED_DEV["krouter-1.0.1"]
    assert _row(bench.score(rows, bench.bm25_answers(rows))) == PUBLISHED_DEV["bm25"]
