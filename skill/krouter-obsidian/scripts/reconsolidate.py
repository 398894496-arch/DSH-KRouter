#!/usr/bin/env python3
"""Nightly trigger learning from the router's own query log (retrieval-driven reconsolidation).

Reads queries the router could not answer well (literal fallback, or low-confidence recall), shows
a model the top recall candidates for each, and asks which page answers it — or none. Accepted
pairs are appended to `下意识触发词-自学习.psv` as `rel|original query`: recall-only, never a lock,
no paraphrase invented. Half of real router calls repeat an earlier question, so one fix pays again.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recall_index as ri  # noqa: E402

MISS = {"bounded-literal-search-complete"}
DEFAULT_OUT = "90 系统文件/自动化/下意识触发词-自学习.psv"
PROMPT = """下面是一个个人知识库路由器没答好的查询。每条给出：查询原文，以及召回排名前列的候选页（路径 + 一句话结论）。
判断哪一个候选页能回答这个查询。规则：
- 只能从该条给出的候选里选，原样输出路径；候选都不对就输出 none。宁可 none，不要硬选。
- 查询问的是库外常识、闲聊、或候选只是碰巧有相同字词，一律 none。
只输出 JSON：{"<id>": "<候选路径或 none>", ...}

"""


def state_dir() -> Path:
    return Path(os.environ.get("KROUTER_STATE_DIR") or Path.home() / ".local" / "state" / "krouter")


def load_misses(log: Path, since: str) -> list[dict]:
    seen: dict[str, dict] = {}
    if not log.is_file():
        return []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("ts", "") <= since:
            continue
        weak = row.get("status") in MISS or row.get("confidence") == "low"
        if weak and row.get("q"):
            seen.setdefault(row["q"].strip(), row)
    return list(seen.values())


def learned(out: Path) -> set[tuple[str, str]]:
    pairs = set()
    if out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "|" in line:
                rel, words = line.split("|", 1)
                pairs.update((rel, w) for w in words.split(";"))
    return pairs


def find_cli(explicit: str) -> str:
    for cand in (explicit, os.environ.get("KROUTER_LEARN_CLI", ""), shutil.which("claude") or "",
                 "/opt/homebrew/bin/claude", str(Path.home() / ".local/bin/claude")):
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    return ""


def ask(cli: str, model: str, prompt: str) -> dict[str, str]:
    argv = [cli, "--print", "--tools", "", "--output-format", "text", "--no-session-persistence"]
    if model:
        argv += ["--model", model]
    proc = subprocess.run(argv + [prompt], capture_output=True, text=True, timeout=900)
    m = re.search(r"\{.*\}", proc.stdout, re.S)
    if proc.returncode != 0 or not m:
        raise SystemExit(f"learner model call failed: {(proc.stderr or proc.stdout)[-300:]}")
    return json.loads(m.group(0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT", ""))
    ap.add_argument("--out", default=os.environ.get("KROUTER_LEARNED_TRIGGERS", DEFAULT_OUT), help="vault-relative")
    ap.add_argument("--cli", default="")
    ap.add_argument("--model", default=os.environ.get("KROUTER_LEARN_MODEL", ""))
    ap.add_argument("--since", default="", help="ISO ts; default = last run cursor")
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.vault:
        print("set OBSIDIAN_VAULT", file=sys.stderr)
        return 2
    vault = Path(args.vault)
    out = vault / args.out
    cursor = state_dir() / "reconsolidate.cursor"
    since = args.since or (cursor.read_text().strip() if cursor.is_file() else "")
    misses = load_misses(state_dir() / "queries.jsonl", since)[: args.max]
    have = learned(out)
    items = []
    for row in misses:
        res = ri.recall(vault, row["q"], limit=8, gate=False)
        cands = [h for h in res["hits"] if h["tier"] != "dead"]
        if cands and not any((h["rel"], row["q"]) in have for h in cands):
            items.append({"id": str(len(items)), "q": row["q"], "cands": cands})
    report = {"misses": len(misses), "asked": len(items), "learned": 0, "none": 0}
    if items and not args.dry_run:
        cli = find_cli(args.cli)
        if not cli:
            print("no logged-in CLI for learning; skipped", file=sys.stderr)
            return 0
        blocks = []
        for it in items:
            lines = "\n".join(f"  - {h['rel']} ｜ {h['how'][:70]}" for h in it["cands"])
            blocks.append(f"### id={it['id']} 查询：{it['q']}\n候选：\n{lines}\n")
        verdict = ask(cli, args.model, PROMPT + "\n".join(blocks))
        new_lines = []
        for it in items:
            pick = (verdict.get(it["id"]) or "none").strip()
            if pick in {h["rel"] for h in it["cands"]}:
                new_lines.append(f"{pick}|{it['q'].replace('|', '／').replace(';', '，')}")
                report["learned"] += 1
            else:
                report["none"] += 1
        if new_lines:
            out.parent.mkdir(parents=True, exist_ok=True)
            head = "" if out.is_file() else (
                "# 夜间自学习触发词（reconsolidate.py）：来自路由器没答好的真实查询，经模型从召回候选中确认。\n"
                "# 只参与召回，不参与锁定；status: provisional。rel|查询原文\n")
            with out.open("a", encoding="utf-8") as fh:
                fh.write(head + "\n".join(new_lines) + "\n")
    if not args.dry_run:
        cursor.parent.mkdir(parents=True, exist_ok=True)
        cursor.write_text(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
