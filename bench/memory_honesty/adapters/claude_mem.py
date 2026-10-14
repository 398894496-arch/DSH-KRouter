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
    # (13.39: hooks call `claude-mem` from $HOME/.local/bin, so put it on PATH; set CLAUDE_MEM_CLAUDE_CONFIG_DIR and
    #  CLAUDE_MEM_OBSERVER_CLAUDE_CONFIG_DIR to a new directory and start the worker with CLAUDE_CODE_OAUTH_TOKEN in its
    #  environment, or it looks up the host's keychain login; heldout3 was read in four sessions, one per top folder)
    python3 bench/memory_honesty/adapters/claude_mem.py --set dev --project benchvault > cm.jsonl
    python3 bench/memory_honesty/run.py --answers cm.jsonl
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("mh_bench_cm", HERE / "run.py")
bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench)
TOPS: tuple[str, ...] = ("Engineering",)


def page_of(path: str) -> str:
    """`/tmp/benchvault/Engineering/X.md` or `Engineering/X.md` → `Engineering/X.md` (any top folder of the vault)."""
    path = path.replace("\\", "/")
    hits = [i for i in (path.find(t + "/") for t in TOPS) if i >= 0 and (i == 0 or path[i - 1] == "/")]
    return path[min(hits):] if hits else ""


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
    ap.add_argument("--set", choices=sorted(bench.SETS), default="dev")
    ap.add_argument("--project", default="benchvault")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--base", default=os.environ.get("CLAUDE_MEM_URL", "http://127.0.0.1:37777"))
    args = ap.parse_args()
    global TOPS
    TOPS = tuple(sorted(p.name for p in bench.vault_of(args.set).iterdir() if p.is_dir()))
    rows = bench.questions(args.set)
    for it in rows:
        cited = ask(args.base, it["q"], args.project, args.limit)
        print(json.dumps({"id": it["id"], "cited": cited, "refused": not cited}, ensure_ascii=False))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
