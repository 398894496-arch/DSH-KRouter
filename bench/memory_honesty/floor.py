#!/usr/bin/env python3
"""Give any scored system the two things a careful user would add: skip superseded pages, refuse below a floor.

The memory honesty bench compares systems at their defaults, and most have no refusal at all, so "neighbours refused
0 / 10" is decided before the first question. This puts every system that reports a score on the same footing as
KRouter: pages whose frontmatter says `status: superseded` are dropped from its results, and a score floor is picked
on the dev set with one fixed rule (most right answers minus wrong citations; on a tie, the lower floor) and applied
unchanged to the target set. For the held-out set only aggregates are printed (HELDOUT.md rule 3).

    python3 bench/memory_honesty/floor.py --dev bm.dev.jsonl --target bm.heldout.jsonl --set heldout

Input lines: {"id", "cited": [page, …], "scores": [score, …]} (higher is better), as the adapters write them.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mh_bench_floor", HERE / "run.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def superseded(vault: Path) -> set[str]:
    out = set()
    for path in vault.rglob("*.md"):
        head = path.read_text(encoding="utf-8").split("\n---", 1)[0]
        if re.search(r"(?m)^status:\s*superseded\s*$", head):
            out.add(path.relative_to(vault).as_posix())
    return out


def scored_of(path: Path, skip: set[str]) -> list[tuple[str, list[tuple[str, float]]]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        hits = [(c, float(s)) for c, s in zip(a.get("cited") or [], a.get("scores") or []) if c not in skip]
        out.append((a["id"], hits))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", required=True, help="the system's scored answers on the dev set")
    ap.add_argument("--target", required=True, help="its scored answers on the set to grade")
    ap.add_argument("--set", choices=sorted(bench.SETS), default="dev", dest="qset")
    ap.add_argument("--dev-set", choices=sorted(bench.SETS), default="",
                    help="the set the --dev answers are on (default: the dev set on the target's vault, dev3 for vault3)")
    ap.add_argument("--ci", action="store_true", help="add 95%% bootstrap intervals")
    args = ap.parse_args()
    dev_set = args.dev_set or bench.floor_dev_of(args.qset)
    dev_rows = bench.questions(dev_set)
    floor = bench.pick_floor(dev_rows, scored_of(Path(args.dev), superseded(bench.vault_of(dev_set))))
    rows = bench.questions(args.qset)
    answers = bench.floor_answers(scored_of(Path(args.target), superseded(bench.vault_of(args.qset))), floor)
    res = bench.score(rows, answers)
    if args.ci:
        res["ci95"] = bench.bootstrap(rows, answers)
    if args.qset in bench.HELDOUT_SETS:
        res = bench.aggregate(res)
    print(json.dumps({"floor_picked_on": dev_set, "floor": round(floor, 4), **res}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
