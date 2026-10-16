#!/usr/bin/env python3
"""Does KRouter write down what was decided? An offline replay of real sessions (registered in HELDOUT.md, set 6).

Takes recorded agent sessions, runs KRouter's own import and distill on them (the step that turns a session into
"what was decided / what changed" lines), and compares those lines with the decisions the host confirms were made.
Nothing new is run in an agent; the only model calls are the distill itself and the judge.

    capture_bench.py pick                      # 10 sessions, stratified by agent, seed 20261016
    capture_bench.py distill --cli /opt/homebrew/bin/claude
    KROUTER_EVAL_KEY=… capture_bench.py propose --openai-base http://127.0.0.1:8317/v1 --model grok-4.7
    capture_bench.py sheet                     # a local page: tick each proposed decision, add the missing ones
    KROUTER_EVAL_KEY=… capture_bench.py score --answers label.json --openai-base … --model grok-4.7

Everything lives in `~/.local/state/krouter-eval/capture/` (private). Prints counts and rates only.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "skill/krouter-obsidian/scripts"))
import classify_asks as ca  # noqa: E402
import import_sessions as imp  # noqa: E402

STATE = Path.home() / ".local/state/krouter-eval/capture"
QUOTA = {"claude-code": 4, "cursor": 3, "codex": 3}
PROPOSE = """下面是一个人和他的编程 agent 某一天的一段会话摘录（只有他的提问和 agent 每轮最后的回答）。
列出这段会话里**真正定下来的事**和**改主意的事**：
- 定下来的事：一个决定、一条规则、一个做法（例：「发版只从 main 打 tag」）。
- 改主意的事：先定了 A，后来改成 B，写成「原来 A → 改成 B」。
只列摘录里明确出现、而且是这个人认可的；agent 自己提议但他没同意的不算；纯粹的操作步骤、临时排查不算。
每条一行，用这个人的说法写清楚，不超过 40 个字。一条都没有就输出空数组。
只输出 JSON 数组：["...", "...", ...]

摘录：

"""
MATCH = """下面是一段会话里"真正定下来的事"（标准答案，编号 G），和某个系统从同一段会话里提炼出的条目（编号 S）。
判断对应关系：一条 S 和一条 G 说的是同一件事、方向也一致（改主意的，改之前和改之后都要对），才算对上。
只输出 JSON：{"matches": [["G1","S2"], ...]}；一条 G 最多对一条 S，一条 S 最多对一条 G。

"""


def entries_of(path: Path, agent: str) -> list[dict]:
    return [e for e in imp.collect(date(2026, 1, 1), date(2026, 12, 31), [path]) if e["agent"] == agent]


def pick() -> int:
    rng = random.Random(20261016)
    pool: dict[str, list[tuple[str, str]]] = {a: [] for a in QUOTA}
    for agent, root in imp.roots().items():
        if agent not in QUOTA or not root.is_dir():
            continue
        for p in sorted(root.rglob("*.jsonl")):
            if "subagents" in p.parts or (agent == "cursor" and "agent-transcripts" not in p.parts):
                continue
            s = {"claude-code": imp.read_claude, "codex": imp.read_codex, "cursor": imp.read_cursor}[agent](p)
            n, answered = len(s["turns"]), sum(1 for t in s["turns"] if t["answer"])
            if 8 <= n <= 60 and answered >= 0.7 * n and "DSH-KRouter" not in s.get("cwd", ""):
                pool[agent].append((str(p), s["turns"][0]["ts"][:10]))
    chosen = []
    for agent, k in QUOTA.items():
        for path, day in rng.sample(sorted(pool[agent]), k):
            chosen.append({"agent": agent, "path": path, "first_day": day})
    STATE.mkdir(parents=True, exist_ok=True)
    out = STATE / "sessions.json"
    out.write_text(json.dumps(chosen, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(out, 0o600)
    print(json.dumps({"sessions": len(chosen), "by_agent": {a: k for a, k in QUOTA.items()},
                      "days": sorted(c["first_day"] for c in chosen)}))
    return 0


def units() -> list[dict]:
    """One unit per (session, day), exactly as the importer pages them: the excerpt KRouter distills."""
    out = []
    for s in json.loads((STATE / "sessions.json").read_text(encoding="utf-8")):
        for e in entries_of(Path(s["path"]), s["agent"]):
            page = imp.render(e)
            out.append({"unit": f"{e['id'][:8]}-{e['day'].isoformat()}", "agent": s["agent"], "entry": e, "page": page,
                        "excerpt": page.split("\n## 摘录", 1)[-1][: imp.DISTILL_MAX]})
    return out


def distill(args) -> int:
    if args.cli:
        os.environ["KROUTER_LEARN_CLI"] = args.cli
    rows = []
    for u in units():
        digest, chars = imp.distill(u["entry"], u["page"], STATE, False)
        rows.append({"unit": u["unit"], "agent": u["agent"],
                     "lines": [re.sub(r"^[-*]\s*", "", ln) for ln in digest.splitlines() if "没有定下来的事" not in ln]})
    out = STATE / "distilled.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    os.chmod(out, 0o600)
    print(json.dumps({"units": len(rows), "lines": sum(len(r["lines"]) for r in rows)}))
    return 0


def call(args, prompt: str) -> str:
    return (ca.ask_api if args.openai_base else ca.ask_cli)(args.openai_base or args.cli, args.model, args.effort, prompt)


def propose(args) -> int:
    rows = []
    for u in units():
        text = call(args, PROPOSE + u["excerpt"])
        m = re.search(r"\[.*\]", text, re.S)
        try:
            items = [str(x)[:80] for x in json.loads(m.group(0))] if m else []
        except ValueError:
            items = []
        rows.append({"unit": u["unit"], "proposed": items})
    out = STATE / "proposed.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    os.chmod(out, 0o600)
    print(json.dumps({"units": len(rows), "proposed": sum(len(r["proposed"]) for r in rows)}))
    return 0


SHEET = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>会话决定核对</title><style>
:root{--bg:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e5e5ea;--card:#f7f7f9;--acc:#0a7d5a}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececf0;--mute:#9a9aa2;--line:#2c2c31;--card:#1c1c20;--acc:#4fd1a5}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"PingFang SC",sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 90px}h1{font-size:22px;margin:0 0 6px}p.note{color:var(--mute)}
section{border-top:1px solid var(--line);padding:18px 0}details{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}
pre{white-space:pre-wrap;word-break:break-word;font:13px/1.55 inherit;margin:6px 0}.item{margin:6px 0}textarea{width:100%;min-height:70px;font:inherit;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);padding:6px}
#bar{position:fixed;left:0;right:0;bottom:0;background:var(--bg);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;justify-content:center;align-items:center}
button{font:inherit;padding:6px 14px;border:1px solid var(--acc);color:var(--acc);background:transparent;border-radius:6px;cursor:pointer}
</style></head><body><main><h1>会话决定核对（__N__ 段）</h1>
<p class="note">每段会话下面是模型列出的候选决定。对的勾「对」，错的或不是你认可的勾「不对」。漏掉的、你确实定了的事，写在下面的框里，一行一条（改主意的写成「原来 A → 改成 B」）。可以展开看会话摘录。</p>
__ITEMS__</main><div id="bar"><span id="done"></span><button onclick="exportIt()">导出</button></div>
<script>
const KEY="krouter-capture-sheet-v1";let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
document.querySelectorAll("input[type=radio]").forEach(r=>{if(st[r.name]===r.value)r.checked=true;r.addEventListener("change",()=>{st[r.name]=r.value;save()})});
document.querySelectorAll("textarea").forEach(t=>{t.value=st[t.name]||"";t.addEventListener("input",()=>{st[t.name]=t.value;save()})});
function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}count()}
function count(){const all=document.querySelectorAll(".item").length;let d=0;document.querySelectorAll(".item").forEach(i=>{if(st[i.dataset.k])d++});document.getElementById("done").textContent=`已核对 ${d} / ${all} 条`}
function exportIt(){const b=new Blob([JSON.stringify(st,null,1)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="capture_sheet_answers.json";a.click()}
count();
</script></body></html>"""


def sheet() -> int:
    proposed = {r["unit"]: r["proposed"] for r in map(json.loads, open(STATE / "proposed.jsonl", encoding="utf-8"))}
    items = []
    for u in units():
        rows = []
        for n, p in enumerate(proposed.get(u["unit"], []), 1):
            k = f"{u['unit']}|P{n}"
            rows.append(f'<div class="item" data-k="{k}">{html.escape(p)}　'
                        f'<label><input type="radio" name="{k}" value="yes"> 对</label> '
                        f'<label><input type="radio" name="{k}" value="no"> 不对</label></div>')
        items.append(f'<section><b>{html.escape(u["unit"])}</b> · {u["agent"]} · {u["entry"]["project"] or "?"}'
                     f'<details><summary>会话摘录</summary><pre>{html.escape(u["excerpt"])}</pre></details>'
                     + ("".join(rows) or "<p class='note'>模型没列出任何决定。</p>")
                     + f'<div>漏掉的（一行一条）：<textarea name="{u["unit"]}|missing"></textarea></div></section>')
    out = STATE / "capture_sheet.html"
    out.write_text(SHEET.replace("__N__", str(len(items))).replace("__ITEMS__", "\n".join(items)), encoding="utf-8")
    os.chmod(out, 0o600)
    print(json.dumps({"sheet": str(out), "units": len(items)}))
    return 0


def score(args) -> int:
    ans = json.loads(Path(args.answers).read_text(encoding="utf-8"))
    proposed = {r["unit"]: r["proposed"] for r in map(json.loads, open(STATE / "proposed.jsonl", encoding="utf-8"))}
    distilled = {r["unit"]: r["lines"] for r in map(json.loads, open(STATE / "distilled.jsonl", encoding="utf-8"))}
    gold_n = lines_n = matched = 0
    changes_gold = changes_hit = 0
    for unit, props in proposed.items():
        gold = [p for n, p in enumerate(props, 1) if ans.get(f"{unit}|P{n}") == "yes"]
        gold += [ln.strip() for ln in (ans.get(f"{unit}|missing") or "").splitlines() if ln.strip()]
        lines = distilled.get(unit, [])
        gold_n += len(gold)
        lines_n += len(lines)
        if not gold or not lines:
            changes_gold += sum("→" in g for g in gold)
            continue
        prompt = MATCH + "\n".join(f"G{i}. {g}" for i, g in enumerate(gold, 1)) + "\n\n" + \
            "\n".join(f"S{i}. {s}" for i, s in enumerate(lines, 1))
        m = re.search(r"\{.*\}", call(args, prompt), re.S)
        try:
            pairs = json.loads(m.group(0)).get("matches", []) if m else []
        except ValueError:
            pairs = []
        gs = {p[0] for p in pairs if isinstance(p, list) and len(p) == 2}
        ss = {p[1] for p in pairs if isinstance(p, list) and len(p) == 2}
        hit = min(len(gs), len(ss))
        matched += hit
        for i, g in enumerate(gold, 1):
            if "→" in g:
                changes_gold += 1
                changes_hit += f"G{i}" in gs
    report = {"gold_decisions": gold_n, "distilled_lines": lines_n, "matched": matched,
              "missed_rate": round(1 - matched / gold_n, 3) if gold_n else None,
              "wrong_rate": round(1 - matched / lines_n, 3) if lines_n else None,
              "changes_in_gold": changes_gold, "changes_captured": changes_hit}
    (STATE / "score.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["pick", "distill", "propose", "sheet", "score"])
    ap.add_argument("--cli", default="")
    ap.add_argument("--openai-base", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--answers", default="")
    args = ap.parse_args()
    return {"pick": lambda: pick(), "distill": lambda: distill(args), "propose": lambda: propose(args),
            "sheet": lambda: sheet(), "score": lambda: score(args)}[args.step]()


if __name__ == "__main__":
    raise SystemExit(main())
