#!/usr/bin/env python3
"""Memory honesty bench: does an agent memory cite the right page, follow corrections, and refuse what it does not hold?

30 questions on a 30-page vault (`vault/`, plain Markdown):
- 10 `correction`: the vault has an old page and a newer page that replaces it; the answer must cite the new one.
- 10 `current`: one page answers it.
- 10 `refuse`: nothing in the vault answers it, but each borrows words from a page that answers a neighbouring
  question (the *search* API timeout, when the vault has the *payments* API timeout). Citing that page is a wrong
  citation, not a near miss.

A system under test is an adapter: a command that reads one question per line on stdin (JSON `{"id", "q"}`) and
writes one JSON line per question: `{"id", "cited": ["Engineering/…md", …], "refused": bool}` — `cited` in rank order,
vault-relative paths. `--adapter krouter` (default) runs KRouter's recall in-process. Score with `--answers FILE` to
grade another system's output.

Metrics
- wrong-citation rate: of the questions a system answered, how many cited something other than the gold page first
  (every answered `refuse` question counts as wrong).
- refusal rate: of the 10 `refuse` questions, how many it refused.
- correction hit rate: of the 10 `correction` questions, how many cited the new page first, not the replaced one.
- current hit rate: of the 10 `current` questions, how many cited the gold page first.

    python3 bench/memory_honesty/run.py                 # KRouter
    python3 bench/memory_honesty/run.py --adapter bm25  # baseline: plain full-text search, always answers
    python3 bench/memory_honesty/run.py --adapter bm25-floor  # + superseded pages skipped + a floor picked on dev
    python3 bench/memory_honesty/run.py --answers other.jsonl

Held-out set (`heldout.jsonl`, rules in `HELDOUT.md`): 25 questions on the same vault, never used for tuning.
`--set heldout` prints aggregate metrics only; which questions were missed stays hidden unless `--reveal`, and a
reveal followed by a ranking or refusal change burns the set (see `HELDOUT.md`).

    python3 bench/memory_honesty/run.py --set heldout
    python3 bench/memory_honesty/run.py --set heldout --adapter bm25
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


SETS = {"dev": "questions.jsonl", "dev2": "questions_dev2.jsonl", "heldout": "heldout.jsonl"}


def questions(name: str = "dev") -> list[dict]:
    path = HERE / SETS[name]
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def aggregate(result: dict) -> dict:
    """The score without per-question detail: what may be looked at on the held-out set."""
    return {k: v for k, v in result.items() if k != "misses"}


def krouter_answers(rows: list[dict]) -> list[dict]:
    sys.path.insert(0, str(REPO / "skill/krouter-obsidian/scripts"))
    saved = {k: os.environ.get(k) for k in ("KROUTER_NO_QUERY_LOG", "KROUTER_CACHE_DIR", "KROUTER_MAP")}
    # Windows 上召回缓存的 SQLite 连接在进程里一直开着，临时目录删不掉也不算失败
    with tempfile.TemporaryDirectory(prefix="krouter-bench-", ignore_cleanup_errors=True) as tmp:
        os.environ["KROUTER_NO_QUERY_LOG"] = "1"
        os.environ["KROUTER_CACHE_DIR"] = str(Path(tmp) / "cache")
        os.environ.pop("KROUTER_MAP", None)
        vault = Path(tmp) / "vault"
        shutil.copytree(HERE / "vault", vault)
        import recall_index as ri

        out = []
        for it in rows:
            res = ri.recall(vault, it["q"], limit=3)
            refused = res["confidence"] == "none" or not res["hits"]
            out.append({"id": it["id"], "refused": refused, "cited": [] if refused else [h["rel"] for h in res["hits"]]})
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return out


def bm25_answers(rows: list[dict]) -> list[dict]:
    """Baseline: plain full-text search (SQLite FTS5, BM25) over the same pages, always answering with its top hit —
    what a memory that "returns the nearest chunk" does. No refusal, no notion of superseded."""
    import re
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE d USING fts5(rel UNINDEXED, body)")
    for path in sorted((HERE / "vault").rglob("*.md")):
        con.execute("INSERT INTO d VALUES (?, ?)", (path.relative_to(HERE / "vault").as_posix(), path.read_text(encoding="utf-8")))
    out = []
    for it in rows:
        words = [w for w in re.findall(r"[a-z0-9]+", it["q"].lower()) if len(w) > 2]
        hits = con.execute("SELECT rel FROM d WHERE d MATCH ? ORDER BY bm25(d) LIMIT 3",
                           (" OR ".join(f'"{w}"' for w in words),)).fetchall() if words else []
        out.append({"id": it["id"], "refused": not hits, "cited": [h[0] for h in hits]})
    return out


def _bm25_index(skip_superseded: bool):
    import re
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE d USING fts5(rel UNINDEXED, body)")
    for path in sorted((HERE / "vault").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if skip_superseded and re.search(r"(?m)^status:\s*superseded\s*$", text.split("\n---", 1)[0]):
            continue
        con.execute("INSERT INTO d VALUES (?, ?)", (path.relative_to(HERE / "vault").as_posix(), text))
    return con


def bm25_scored(rows: list[dict], skip_superseded: bool = True) -> list[tuple[str, list[tuple[str, float]]]]:
    """[(id, [(page, score)])] — BM25 over the pages, superseded pages left out, score = -bm25 (higher is better)."""
    import re

    con = _bm25_index(skip_superseded)
    out = []
    for it in rows:
        words = [w for w in re.findall(r"[a-z0-9]+", it["q"].lower()) if len(w) > 2]
        hits = con.execute("SELECT rel, -bm25(d) FROM d WHERE d MATCH ? ORDER BY bm25(d) LIMIT 3",
                           (" OR ".join(f'"{w}"' for w in words),)).fetchall() if words else []
        out.append((it["id"], [(r, float(sc)) for r, sc in hits]))
    return out


def floor_answers(scored: list[tuple[str, list[tuple[str, float]]]], floor: float) -> list[dict]:
    out = []
    for qid, hits in scored:
        ok = bool(hits) and hits[0][1] >= floor
        out.append({"id": qid, "refused": not ok, "cited": [h[0] for h in hits] if ok else []})
    return out


def pick_floor(rows: list[dict], scored) -> float:
    """The floor a careful baseline would pick on the dev set: most right answers minus wrong citations; on a tie, the
    lower floor (answer more). Picked on dev only, then applied unchanged to held-out."""
    cands = sorted({0.0} | {h[0][1] for _, h in scored if h})
    best, best_floor = None, 0.0
    for f in cands:
        res = score(rows, floor_answers(scored, f))
        right = int(res["correction_hit"].split("/")[0]) + int(res["current_hit"].split("/")[0])
        util = right - res["wrong_citations"]
        if best is None or util > best:
            best, best_floor = util, f
    return best_floor


def bm25_floor_answers(rows: list[dict]) -> list[dict]:
    """Baseline with the two things anyone would add to full-text search: superseded pages left out, and a score floor
    below which it refuses. The floor is picked on the dev set (`pick_floor`) and applied as is to any set."""
    dev = questions("dev")
    floor = pick_floor(dev, bm25_scored(dev))
    return floor_answers(bm25_scored(rows), floor)


def score(rows: list[dict], answers: list[dict]) -> dict:
    by_id = {a["id"]: a for a in answers}
    answered = wrong = refused_ok = corr_ok = cur_ok = 0
    detail = []
    for it in rows:
        a = by_id.get(it["id"], {"refused": True, "cited": []})
        top = None if a.get("refused") else (a.get("cited") or [None])[0]
        if top is not None:
            answered += 1
            wrong += top != it["gold"]
        if it["kind"] == "refuse":
            refused_ok += top is None
        elif it["kind"] == "correction":
            corr_ok += top == it["gold"]
        else:
            cur_ok += top == it["gold"]
        ok = top == it["gold"] if it["gold"] else top is None
        detail.append({"id": it["id"], "ok": ok, "top": top})
    n = {k: sum(1 for r in rows if r["kind"] == k) for k in ("refuse", "correction", "current")}
    return {"questions": len(rows), "answered": answered, "wrong_citations": wrong,
            "wrong_citation_rate": round(wrong / answered, 3) if answered else 0.0,
            "refused": f"{refused_ok}/{n['refuse']}", "correction_hit": f"{corr_ok}/{n['correction']}",
            "current_hit": f"{cur_ok}/{n['current']}", "misses": [d for d in detail if not d["ok"]]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--answers", help="grade this JSONL instead of running KRouter")
    ap.add_argument("--adapter", choices=["krouter", "bm25", "bm25-floor"], default="krouter")
    ap.add_argument("--set", choices=sorted(SETS), default="dev", dest="qset",
                    help="dev: the 30 bench questions (tune on these); heldout: never tune on these (HELDOUT.md)")
    ap.add_argument("--reveal", action="store_true",
                    help="held-out only: also print which questions were missed. Changing ranking or refusal after "
                         "this burns the set; record it in HELDOUT.md")
    args = ap.parse_args()
    rows = questions(args.qset)
    if args.answers:
        answers = [json.loads(x) for x in Path(args.answers).read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        answers = {"krouter": krouter_answers, "bm25": bm25_answers, "bm25-floor": bm25_floor_answers}[args.adapter](rows)
    result = score(rows, answers)
    if args.qset == "heldout" and not args.reveal:
        result = aggregate(result)
    elif args.qset == "heldout":
        print("held-out per-question results revealed: if ranking or refusal changes after this, the set is burned "
              "(bench/memory_honesty/HELDOUT.md)", file=sys.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
