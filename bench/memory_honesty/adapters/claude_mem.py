#!/usr/bin/env python3
"""Adapter: claude-mem (github.com/thedotmack/claude-mem) on the memory honesty bench.

claude-mem does not index a folder; it remembers what happens in Claude Code sessions. So it learns the bench vault
the way a user's claude-mem learns their docs: a Claude Code session in a copy of the vault reads every page (one
Read per page), and claude-mem's observer turns each read into an observation that names the file it read. Then each
question goes to claude-mem's own search (`/api/search`, what its MCP search tool calls), and each result maps back
to the page through the observation's `files_read`. Its defaults are used. A question counts as refused only when the
search returns nothing that maps to a page, since that is the only refusal it has.

Setup used for docs/BENCHMARK.md (claude-mem 13.35.0, observer model claude-haiku-4-5, in an isolated HOME):

    cp -R bench/memory_honesty/vault /tmp/benchvault && cd /tmp/benchvault && git init && git add -A && git commit -m vault
    claude -p --allowedTools "Read Glob" "Read every .md file under Engineering/, one file per Read call, then list each rule."
    # wait until claude-mem's processing queue is empty, then:
    python3 bench/memory_honesty/adapters/claude_mem.py --set dev --project benchvault > cm.jsonl
    python3 bench/memory_honesty/run.py --answers cm.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SETS = {"dev": "questions.jsonl", "heldout": "heldout.jsonl"}


def page_of(path: str) -> str:
    """`/tmp/benchvault/Engineering/X.md` or `Engineering/X.md` → `Engineering/X.md`."""
    path = path.replace("\\", "/")
    i = path.find("Engineering/")
    return path[i:] if i >= 0 else ""


def ask(base: str, q: str, project: str, limit: int) -> list[str]:
    url = f"{base}/api/search?" + urllib.parse.urlencode({"query": q, "project": project, "limit": limit, "format": "json"})
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = json.load(resp)
    cited: list[str] = []
    for o in data.get("observations") or []:
        try:
            files = json.loads(o.get("files_read") or "[]") + json.loads(o.get("files_modified") or "[]")
        except ValueError:
            files = []
        for f in files:
            page = page_of(str(f))
            if page and page not in cited:
                cited.append(page)
    return cited


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), default="dev")
    ap.add_argument("--project", default="benchvault")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--base", default=os.environ.get("CLAUDE_MEM_URL", "http://127.0.0.1:37777"))
    args = ap.parse_args()
    rows = [json.loads(x) for x in (HERE / SETS[args.set]).read_text(encoding="utf-8").splitlines() if x.strip()]
    for it in rows:
        cited = ask(args.base, it["q"], args.project, args.limit)
        print(json.dumps({"id": it["id"], "cited": cited, "refused": not cited}, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
