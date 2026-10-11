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
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402
import recall_index as ri  # noqa: E402

CARDS = "90 系统文件/自动化/下意识问答.jsonl"
PAGE_MAX = 3500
BATCH = 6
# 卡片写进库前过滤：像密钥、token、口令的串一律丢弃（prompt 里的"不写密钥"不算保证）
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|\b[A-Za-z0-9_-]{32,}\b|bearer\s+\S+|api[_-]?key\s*[=:]|password\s*[=:]|token\s*[=:])", re.I)
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
            if row.get("rel") and (row.get("empty") or (row.get("q") and row.get("a"))):
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


def ask(vault: Path, rels: list[str]) -> dict:
    prompt = PROMPT + "\n".join(block(vault, r) for r in rels)
    last = ""
    for _ in range(2):
        try:
            text = llm.complete(prompt, vault)
        except RuntimeError as exc:  # NoModel is a RuntimeError: propagate so the run is skipped, not emptied
            if isinstance(exc, llm.NoModel):
                raise
            last = str(exc)
            continue
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return {k: v for k, v in json.loads(m.group(0)).items() if k in rels and isinstance(v, list)}
            except json.JSONDecodeError:
                last = "model output was not JSON"
    print(f"batch failed at {rels[0]}: {last[-200:]}", file=sys.stderr)
    return {}


def accept(item: object, page_text: str) -> str:
    """'' if the card is kept, else the reason it is dropped."""
    if not isinstance(item, dict) or not item.get("q") or not item.get("a"):
        return "malformed"
    if SECRET_RE.search(item["q"] + " " + item["a"]):
        return "secret-like"
    if not ri.faithful(item["a"], page_text):
        return "not-verbatim"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("OBSIDIAN_VAULT", ""))
    ap.add_argument("--cli", default="", help="pick a CLI explicitly (goes before any API key)")
    ap.add_argument("--model", default="")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="only the first N stale pages (0 = all)")
    args = ap.parse_args()
    if args.cli:
        os.environ["KROUTER_LEARN_CLI"] = args.cli
    if args.model:
        os.environ["KROUTER_LEARN_MODEL"] = args.model
    vault = Path(args.vault)
    out = vault / CARDS
    cards = load_cards(vault)
    pages = targets(vault)
    sha = {rel: page_sha(vault / rel) for rel in pages}
    fresh = {c["rel"] for c in cards if sha.get(c["rel"]) == c.get("sha")}
    keep = [c for c in cards if c["rel"] in fresh]
    stale = [rel for rel in pages if rel not in fresh]
    if args.limit:
        stale = stale[: args.limit]
    batches = [stale[i : i + BATCH] for i in range(0, len(stale), BATCH)]
    made = empty = 0
    dropped: dict[str, int] = {}
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            parts = list(ex.map(lambda b: ask(vault, b), batches))
    except llm.NoModel as exc:
        print(f"answer cards skipped: {exc}", file=sys.stderr)
        return 0
    for part in parts:
        for rel, items in part.items():
            page_text = (vault / rel).read_text(encoding="utf-8", errors="replace")
            good = []
            for it in items:
                why = accept(it, page_text)
                if why:
                    dropped[why] = dropped.get(why, 0) + 1
                else:
                    good.append(it)
            if not good:
                # 导航页或全被拦下：记下这页的哈希，页面不变就不再每晚重问
                keep.append({"rel": rel, "sha": sha[rel], "empty": True})
                empty += 1
            for it in good[:5]:
                keep.append({"rel": rel, "sha": sha[rel], "q": it["q"].strip(), "a": it["a"].strip()[:160]})
                made += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in keep), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"pages": len(pages), "stale": len(stale), "cards_written": made, "dropped": dropped,
                      "pages_without_cards": empty, "cards_total": sum(1 for c in keep if not c.get("empty"))},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
