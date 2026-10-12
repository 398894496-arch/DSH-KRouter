"""Memory honesty bench (bench/memory_honesty): no wrong citation, every neighbour question refused, corrections win.

The bench became a development set the day it was written: its first run found the English function-word bug
fixed in 0.13.0 (see docs/BENCHMARK.md for the before / after). The floors below only go up.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mh_bench", REPO / "bench/memory_honesty/run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_krouter_on_memory_honesty_bench():
    rows = bench.questions()
    res = bench.score(rows, bench.krouter_answers(rows))
    assert res["wrong_citations"] == 0, res["misses"]
    assert res["refused"] == "10/10", res["misses"]
    assert int(res["correction_hit"].split("/")[0]) >= 8, res["misses"]
    assert int(res["current_hit"].split("/")[0]) >= 9, res["misses"]


def test_plain_full_text_baseline_is_what_the_bench_is_for():
    """Sanity check of the bench itself: a search that always answers cites wrong pages and old decisions."""
    rows = bench.questions()
    res = bench.score(rows, bench.bm25_answers(rows))
    assert res["refused"] == "0/10" and res["wrong_citations"] >= 10
