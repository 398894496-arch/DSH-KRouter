"""Third memory honesty bench: vault3/ (110 pages, English and Chinese, with daily logs) and heldout3 (200 questions).

Held-out only: nobody tunes on vault3. Rules and the pre-registered decision rule: bench/memory_honesty/HELDOUT.md,
"Held-out set 3". As with sets 1 and 2 there is no floor on the held-out score. What is checked:

- heldout3 and vault3 are frozen (normalized SHA-256);
- shape: 200 questions, 100 per language, 60 corrections / 60 current / 80 neighbours;
- soundness: each answerable question's `evidence` is on its gold page, each replaced page says superseded, and each
  neighbour question's `absent` term is in the question and on no page of vault3 (logs included; English plurals
  count), so no neighbour question can be answered by accident;
- no question repeats a question from another set;
- the statistics helpers (bootstrap intervals, coverage curve) behave on a tiny known case;
- a sanity guard far from any target: KRouter cites wrong pages less often and refuses more neighbours than plain BM25.

Messages carry aggregates only.
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
VAULT3 = HERE / "vault3"
spec = importlib.util.spec_from_file_location("mh_bench_v3", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

# Frozen 2026-10-13 on main 792c74e. Do not update these to make a change pass: see HELDOUT.md.
HELDOUT3_SHA256 = "cd21250210c4fc10685a4bd08b9ec40812618012ee48b8d6d4a42537929387a8"
VAULT3_SHA256 = "ab8603d25f224287d77195a8c4e77abaf05b22e42bd5e0e7c61c46b1595b8ded"


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _pages() -> dict[str, str]:
    return {p.relative_to(VAULT3).as_posix(): p.read_text(encoding="utf-8") for p in VAULT3.rglob("*.md")}


def _has(term: str, text: str) -> bool:
    if re.search(r"[一-鿿]", term):
        return term in text
    return re.search(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?:s|es)?(?![a-z0-9])", text.lower()) is not None


def test_heldout3_and_vault3_are_frozen():
    got = hashlib.sha256(_norm(gzip.decompress((HERE / "heldout3.jsonl.gz").read_bytes()))).hexdigest()
    assert got == HELDOUT3_SHA256, "heldout3 changed: retire it and add a new set instead (HELDOUT.md)"
    h = hashlib.sha256()
    for p in sorted(VAULT3.rglob("*.md"), key=lambda p: p.relative_to(VAULT3).as_posix()):
        h.update(p.relative_to(VAULT3).as_posix().encode() + b"\0" + _norm(p.read_bytes()) + b"\0")
    assert h.hexdigest() == VAULT3_SHA256, "vault3 changed: log it in HELDOUT.md and re-pin with the reason, or revert"


def test_shape():
    rows = bench.questions("heldout3")
    assert len(rows) == 200
    assert Counter(r["kind"] for r in rows) == {"correction": 60, "current": 60, "refuse": 80}
    assert Counter(r["lang"] for r in rows) == {"en": 100, "zh": 100}
    assert len(_pages()) == 110


def test_every_question_is_sound():
    pages = _pages()
    problems = 0
    for r in bench.questions("heldout3"):
        if r["kind"] == "refuse":
            problems += r["gold"] is not None or r["neighbor"] not in pages or not _has(r["absent"], r["q"])
            problems += any(_has(r["absent"], text) for text in pages.values())
        else:
            problems += r["evidence"] not in pages.get(r["gold"], "")
            if r["kind"] == "correction":
                problems += "status: superseded" not in pages.get(r["stale"], "")
    assert problems == 0, f"{problems} unsound questions"


def test_no_question_repeats_another_set():
    seen: dict[str, str] = {}
    for name in ("dev", "dev2", "heldout", "dev3", "heldout2", "heldout3"):
        for r in bench.questions(name):
            key = " ".join(r["q"].lower().split())
            assert key not in seen, f"a {name} question repeats a {seen.get(key)} question"
            seen[key] = name


def test_statistics_helpers_on_a_known_case():
    rows = [{"id": str(i), "kind": "current", "q": "", "gold": "a.md"} for i in range(8)] + \
           [{"id": f"r{i}", "kind": "refuse", "q": "", "gold": None} for i in range(4)]
    perfect = [{"id": str(i), "refused": False, "cited": ["a.md"], "score": 10.0 - i} for i in range(8)]
    sloppy = perfect + [{"id": f"r{i}", "refused": False, "cited": ["b.md"], "score": 0.5} for i in range(4)]
    ci = bench.bootstrap(rows, perfect, sloppy, n=300)
    assert ci["wrong_citation_rate"] == [0.0, 0.0]
    assert ci["delta_wrong_citation_rate"][1] < 0  # perfect is always better than sloppy
    assert bench.bootstrap(rows, perfect, n=50) == bench.bootstrap(rows, perfect, n=50)  # fixed seed
    pts = bench.curve(rows, sloppy, points=3)
    assert pts[-1]["answered"] == 12 and pts[-1]["wrong_citations"] == 4 and pts[0]["wrong_citations"] == 0


def test_heldout3_sanity_guard_against_plain_bm25():
    rows = bench.questions("heldout3")
    src = bench.vault_of("heldout3")
    kr = bench.aggregate(bench.score(rows, bench.krouter_answers(rows, src)))
    bm = bench.aggregate(bench.score(rows, bench.bm25_answers(rows, src, cjk=True)))
    msg = f"heldout3 aggregates: krouter={kr} bm25={bm}"
    assert kr["wrong_citation_rate"] < bm["wrong_citation_rate"], msg
    assert int(kr["refused"].split("/")[0]) > int(bm["refused"].split("/")[0]), msg
    print(msg)
