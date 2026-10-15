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
    "bm25-floor": (3, 22, "7/10", "9/10", "10/10"),
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


def test_bm25_floor_baseline_picks_its_floor_on_dev_and_matches_the_published_row():
    rows = bench.questions("dev")
    assert _row(bench.score(rows, bench.bm25_floor_answers(rows))) == PUBLISHED_DEV["bm25-floor"]
    assert round(bench.pick_floor(rows, bench.bm25_scored(rows)), 3) == 4.407


def test_floor_tool_on_stored_basic_memory_scores():
    """docs/BENCHMARK.md matched-baseline row for basic-memory, dev side: skip superseded + dev floor."""
    import subprocess
    import sys

    path = RESULTS / "basic-memory-0.22.1.dev.jsonl"
    out = subprocess.run([sys.executable, str(REPO / "bench/memory_honesty/floor.py"), "--dev", str(path), "--target",
                          str(path), "--set", "dev"], capture_output=True, text=True, timeout=120)
    res = json.loads(out.stdout)
    assert (res["wrong_citations"], res["answered"], res["refused"], res["correction_hit"]) == (4, 24, "6/10", "10/10")


HELDOUT3 = REPO / "bench/memory_honesty/results/2026-10-14"
PUBLISHED_HELDOUT3 = {  # docs/BENCHMARK.md「Other memory systems on the same 200 questions」, aggregates only
    "claude-mem-13.39.0": {"wrong_citations": 128, "answered": 200, "refused": "0/80", "right": 72},
    "basic-memory-0.23.2": {"wrong_citations": 155, "answered": 200, "refused": "0/80", "right": 45},
}


def test_heldout3_competitor_rows_regrade_from_stored_output():
    """Anyone can regrade the published heldout3 rows: `run.py --set heldout3 --answers <file>`."""
    rows = bench.questions("heldout3")
    for name, want in PUBLISHED_HELDOUT3.items():
        answers = [json.loads(x) for x in (HELDOUT3 / f"{name}.heldout3.jsonl").read_text(encoding="utf-8").splitlines()
                   if x.strip()]
        r = bench.aggregate(bench.score(rows, answers))
        right = int(r["correction_hit"].split("/")[0]) + int(r["current_hit"].split("/")[0])
        assert {"wrong_citations": r["wrong_citations"], "answered": r["answered"], "refused": r["refused"],
                "right": right} == want, name
