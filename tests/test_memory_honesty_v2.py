"""Second memory honesty bench: vault2/ (60 pages, English and Chinese), dev3 (tune on it) and heldout2 (never).

Rules: bench/memory_honesty/HELDOUT.md, "Held-out set 2". Like set 1, these tests keep the sets honest; they set no
floor on the held-out score. What is checked:

- dev3, heldout2 and vault2 are frozen (normalized SHA-256);
- every answerable question's `evidence` sentence is on its gold page, every replaced page says superseded, and every
  neighbour question's `absent` term is on no page of vault2, so it cannot be answered by accident;
- no question repeats another set's question;
- the plain baseline is what the bench is for (it cites wrong pages and old decisions), and KRouter clears a sanity
  guard far from any target: fewer wrong citations and more refusals than plain BM25 on heldout2.

Messages carry aggregates only, never a held-out question.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HERE = REPO / "bench/memory_honesty"
VAULT2 = HERE / "vault2"
spec = importlib.util.spec_from_file_location("mh_bench_v2", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

# Frozen 2026-10-12 at main f9d0be9. Do not update these to make a change pass: see HELDOUT.md.
DEV3_SHA256 = "66459a9638b354482ee4edc6eb22e2466494ccc38ef9c21135de1c2a4cefd1b3"
HELDOUT2_SHA256 = "0545caa8368ccf01d839e2549a96bb4c75989e49883a8ea16184c69a017fb88e"
VAULT2_SHA256 = "f230a39bb242d285a09f577b49a488f6916c5670c639fb50087e315c553f0ea7"


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _pages() -> dict[str, str]:
    return {p.relative_to(VAULT2).as_posix(): p.read_text(encoding="utf-8") for p in VAULT2.rglob("*.md")}


def _has(term: str, text: str) -> bool:
    if re.search(r"[一-鿿]", term):
        return term in text
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(term.lower()) + r"(?![A-Za-z0-9])", text.lower()) is not None


def test_dev3_heldout2_and_vault2_are_frozen():
    assert hashlib.sha256(_norm((HERE / "questions_dev3.jsonl").read_bytes())).hexdigest() == DEV3_SHA256, \
        "questions_dev3.jsonl changed (HELDOUT.md)"
    got = hashlib.sha256(_norm(gzip.decompress((HERE / "heldout2.jsonl.gz").read_bytes()))).hexdigest()
    assert got == HELDOUT2_SHA256, "heldout2 changed: retire it and add a new set instead (HELDOUT.md)"
    h = hashlib.sha256()
    for p in sorted(VAULT2.rglob("*.md"), key=lambda p: p.relative_to(VAULT2).as_posix()):
        h.update(p.relative_to(VAULT2).as_posix().encode() + b"\0" + _norm(p.read_bytes()) + b"\0")
    assert h.hexdigest() == VAULT2_SHA256, "vault2 changed: log it in HELDOUT.md and re-pin with the reason, or revert"


def test_shape_is_what_the_sets_were_written_with():
    for name in ("dev3", "heldout2"):
        rows = bench.questions(name)
        assert len(rows) == 50, name
        assert Counter(r["kind"] for r in rows) == {"correction": 15, "current": 15, "refuse": 20}, name
        assert Counter(r["lang"] for r in rows) == {"en": 25, "zh": 25}, name
    assert len(_pages()) == 60


def test_every_question_is_sound():
    pages = _pages()
    for name in ("dev3", "heldout2"):
        problems = 0
        for r in bench.questions(name):
            if r["kind"] == "refuse":
                problems += r["gold"] is not None or r["neighbor"] not in pages
                problems += any(_has(r["absent"], text) for text in pages.values())
            else:
                problems += r["evidence"] not in pages.get(r["gold"], "")
                if r["kind"] == "correction":
                    problems += "status: superseded" not in pages.get(r["stale"], "")
        assert problems == 0, f"{name}: {problems} unsound questions"


def test_no_question_repeats_another_set():
    def norm(q: str) -> str:
        return " ".join(q.lower().split())

    seen: dict[str, str] = {}
    for name in ("dev", "dev2", "heldout", "dev3", "heldout2"):
        for r in bench.questions(name):
            key = norm(r["q"])
            assert key not in seen, f"a {name} question repeats a {seen.get(key)} question"
            seen[key] = name


def test_plain_bm25_is_what_the_bench_is_for_on_vault2():
    rows = bench.questions("dev3")
    res = bench.score(rows, bench.bm25_answers(rows, bench.vault_of("dev3"), cjk=True))
    assert int(res["refused"].split("/")[0]) <= 2 and res["wrong_citations"] >= 20, bench.aggregate(res)


def test_heldout2_sanity_guard_against_plain_bm25():
    rows = bench.questions("heldout2")
    src = bench.vault_of("heldout2")
    kr = bench.aggregate(bench.score(rows, bench.krouter_answers(rows, src)))
    bm = bench.aggregate(bench.score(rows, bench.bm25_answers(rows, src, cjk=True)))
    msg = f"heldout2 aggregates: krouter={kr} bm25={bm}"
    assert kr["wrong_citation_rate"] < bm["wrong_citation_rate"], msg
    assert int(kr["refused"].split("/")[0]) > int(bm["refused"].split("/")[0]), msg
    print(msg)
