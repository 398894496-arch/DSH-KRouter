#!/usr/bin/env python3
"""Answer cards (sleep-time compute): precompute the questions a page will be asked, and its answers.

Real router traffic repeats itself (half the calls repeat an earlier question), so the questions are
predictable. For every rule / topic page, a model writes 3–5 `question → one-line answer` pairs taken
only from that page. Cards live in `90 系统文件/自动化/下意识问答.jsonl` (machine file; no source page
is edited), carry the page's content hash, and are rewritten only when the page changes. The router
uses card questions as recall triggers and prints the best-matching card as `answer:` with its source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recall_index as ri  # noqa: E402

CARDS = "90 系统文件/自动化/下意识问答.jsonl"
PAGE_MAX = 3500
BATCH = 6
PROMPT = """下面是个人知识库里的若干页面。为每一页写 3–5 张「问答卡」：用户以后最可能怎么问这一页能回答的问题，以及一句话答案。
规则：
- 问题：口语化中文，像用户随口问 Agent，6–20 字；覆盖这一页不同的要点，不要五张卡问同一件事。
- 答案：只能来自这一页原文，一到两句、不超过 90 字，写结论和关键细节（数字、路径、命令、日期、谁说的），不要写"见本页""详见"。
- 这一页只是导航/索引、没有可回答的结论，就给空数组。
- 不写密钥、token、密码、私人财务细节。
只输出 JSON：{"<页面路径>": [{"q": "...", "a": "..."}, ...], ...}

"""


def page_sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def load_cards(vault: Path) -> list[dict]:
    out = []
    for path in sorted((vault / "90 系统文件").rglob("下意识问答*.jsonl")) if (vault / "90 系统文件").is_dir() else []:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("rel") and row.get("q") and row.get("a"):
                out.append(row)
    return out


def targets(vault: Path) -> list[str]:
    con = ri.connect(ri.cache_path(vault))
    ri.refresh(vault, con)
    return [r for (r,) in con.execute("SELECT rel FROM docs WHERE tier IN ('rule', 'topic') ORDER BY rel")]


def block(vault: Path, rel: str) -> str:
    _meta, body = ri.split_frontmatter((vault / rel).read_text(encoding="utf-8", errors="replace"))
    body = re.sub(r"\n{3,}", "\n\n", body).strip()[:PAGE_MAX]
    return f"### 页面路径: {rel}\n{body}\n"


def ask(cli: str, model: str, vault: Path, rels: list[str]) -> dict:
    argv = [cli, "--print", "--tools", "", "--output-format", "text", "--no-session-persistence"]
    if model:
        argv += ["--model", model]
    prompt = PROMPT + "\n".join(block(vault, r) for r in rels)
    for _ in range(2):
        proc = subprocess.run(argv + [prompt], capture_output=True, text=True, timeout=900)
        m = re.search(r"\{.*\}", proc.stdout, re.S)
        if proc.returncode == 0 and m:
            try:
                return {k: v for k, v in json.loads(m.group(0)).items() if k in rels and isinstance(v, list)}
            except json.JSONDecodeError:
                pass
    print(f"batch failed at {rels[0]}: {(proc.stderr or proc.stdout)[-200:]}", file=sys.stderr)
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT", ""))
    ap.add_argument("--cli", default=os.environ.get("KROUTER_LEARN_CLI", "/opt/homebrew/bin/claude"))
    ap.add_argument("--model", default=os.environ.get("KROUTER_LEARN_MODEL", ""))
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="only the first N stale pages (0 = all)")
    args = ap.parse_args()
    vault = Path(args.vault)
    out = vault / CARDS
    cards = load_cards(vault)
    pages = targets(vault)
    sha = {rel: page_sha(vault / rel) for rel in pages}
    fresh = {(c["rel"]) for c in cards if sha.get(c["rel"]) == c.get("sha")}
    keep = [c for c in cards if c["rel"] in fresh]
    stale = [rel for rel in pages if rel not in fresh]
    if args.limit:
        stale = stale[: args.limit]
    batches = [stale[i : i + BATCH] for i in range(0, len(stale), BATCH)]
    made = empty = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for part in ex.map(lambda b: ask(args.cli, args.model, vault, b), batches):
            for rel, items in part.items():
                good = [it for it in items if isinstance(it, dict) and it.get("q") and it.get("a")]
                empty += not good
                for it in good[:5]:
                    keep.append({"rel": rel, "sha": sha[rel], "q": it["q"].strip(), "a": it["a"].strip()[:160]})
                    made += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in keep), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"pages": len(pages), "stale": len(stale), "cards_written": made,
                      "pages_without_cards": empty, "cards_total": len(keep)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
