"""Held-out set of the memory honesty bench (bench/memory_honesty/heldout.jsonl). Rules: bench/memory_honesty/HELDOUT.md.

These tests keep the set honest; they do not grade KRouter against a target. There is deliberately no floor on the
held-out score: a floor is something to tune toward. What is checked:

- the questions, golds and the bench vault are frozen (normalized SHA-256): changing either one is a visible edit to
  this file, which HELDOUT.md says must come with a burn-log entry;
- the set does not overlap the development questions;
- every gold / stale path exists, and the kinds are what the set was written with;
- a sanity guard far from any tuning target: KRouter must cite wrong pages less often, and refuse neighbours at
  least as often, as plain full-text search that always answers, on the same run.

Assertion messages carry aggregate numbers only, never which question was missed.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "bench/memory_honesty"
spec = importlib.util.spec_from_file_location("mh_bench_heldout", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

# Frozen 2026-10-12 at KRouter 1.0.1 (8c2e0cb). Do not update these to make a change pass: see HELDOUT.md.
HELDOUT_SHA256 = "4ce6fe8f2fd900e4ce77ea6a16cb9732d9d5aadad6bce886200ee6ce0ca60a2b"
VAULT_SHA256 = "304604b9070db205b4b5fe24109b37f82660503c20b8f0cabefd42036faea1be"


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")  # a Windows checkout may convert line endings


def _vault_sha() -> str:
    h = hashlib.sha256()
    root = HERE / "vault"
    for p in sorted(root.rglob("*.md"), key=lambda p: p.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + _norm(p.read_bytes()) + b"\0")
    return h.hexdigest()


def test_heldout_questions_are_frozen():
    got = hashlib.sha256(_norm((HERE / "heldout.jsonl").read_bytes())).hexdigest()
    assert got == HELDOUT_SHA256, "heldout.jsonl changed: retire the set and add a new one instead (HELDOUT.md)"


def test_bench_vault_is_frozen_for_the_heldout_set():
    assert _vault_sha() == VAULT_SHA256, (
        "bench/memory_honesty/vault changed: the held-out numbers no longer mean what they meant. "
        "Record it in HELDOUT.md's log and re-pin with the reason, or revert")


def test_heldout_shape_and_disjoint_from_dev():
    held, dev = bench.questions("heldout"), bench.questions("dev")
    assert len(held) == 25
    kinds = {k: sum(1 for r in held if r["kind"] == k) for k in ("correction", "current", "refuse")}
    assert kinds == {"correction": 9, "current": 6, "refuse": 10}

    def norm(q: str) -> str:
        return " ".join(q.lower().split())

    assert not {r["id"] for r in held} & {r["id"] for r in dev}
    assert not {norm(r["q"]) for r in held} & {norm(r["q"]) for r in dev}
    for r in held:
        for path in (r["gold"], r["stale"]):
            assert path is None or (HERE / "vault" / path).is_file(), r["id"]
        assert (r["gold"] is None) == (r["kind"] == "refuse"), r["id"]


def test_heldout_sanity_guard_against_plain_full_text_search():
    rows = bench.questions("heldout")
    kr = bench.aggregate(bench.score(rows, bench.krouter_answers(rows)))
    bm = bench.aggregate(bench.score(rows, bench.bm25_answers(rows)))
    msg = f"held-out aggregates: krouter={kr} bm25={bm}"
    assert kr["wrong_citation_rate"] < bm["wrong_citation_rate"], msg
    assert int(kr["refused"].split("/")[0]) >= int(bm["refused"].split("/")[0]), msg
    print(msg)
