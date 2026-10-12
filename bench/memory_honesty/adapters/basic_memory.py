#!/usr/bin/env python3
"""Adapter: basic-memory (github.com/basicmachines-co/basic-memory) on the memory honesty bench.

Index the bench vault as a basic-memory project, then ask each question with its own search tool and write one answer
line per question. basic-memory's defaults are used; `--mode hybrid` / `--mode vector` pick its other retrieval modes.
A question counts as refused only when the search returns nothing, since that is the only refusal basic-memory has.

    export HOME=$(mktemp -d)            # keep basic-memory's config and index out of your own
    basic-memory project add bench bench/memory_honesty/vault && basic-memory project default bench
    basic-memory reindex --project bench
    python3 bench/memory_honesty/adapters/basic_memory.py --set dev > bm.jsonl
    python3 bench/memory_honesty/run.py --answers bm.jsonl

`BASIC_MEMORY_CMD` overrides the command (default `basic-memory`; e.g. `uvx --from basic-memory basic-memory`).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SETS = {"dev": "questions.jsonl", "heldout": "heldout.jsonl"}


def ask(cmd: list[str], q: str, mode: str, project: str) -> list[tuple[str, float]]:
    argv = [*cmd, "tool", "search-notes", q, "--page-size", "3", "--project", project]
    if mode != "default":
        argv.append(f"--{mode}")
    out = subprocess.run(argv, capture_output=True, text=True, timeout=300).stdout
    try:
        data = json.loads(out[out.index("{"):])
    except ValueError:
        return []
    cited: list[tuple[str, float]] = []
    for r in data.get("results") or []:
        path = r.get("file_path") or ""
        if path and path not in [c for c, _ in cited]:
            cited.append((path, float(r.get("score") or 0.0)))
    return cited


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), default="dev")
    ap.add_argument("--mode", choices=["default", "hybrid", "vector"], default="default")
    ap.add_argument("--project", default="bench")
    args = ap.parse_args()
    cmd = shlex.split(os.environ.get("BASIC_MEMORY_CMD", "basic-memory"))
    rows = [json.loads(x) for x in (HERE / SETS[args.set]).read_text(encoding="utf-8").splitlines() if x.strip()]
    for it in rows:
        hits = ask(cmd, it["q"], args.mode, args.project)
        # scores 和 cited 一一对应：floor.py 用它在开发集上选下限（docs/BENCHMARK.md「Matched baselines」）
        print(json.dumps({"id": it["id"], "cited": [c for c, _ in hits], "scores": [sc for _, sc in hits],
                          "refused": not hits}, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
