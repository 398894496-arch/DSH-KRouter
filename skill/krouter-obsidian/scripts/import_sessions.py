#!/usr/bin/env python3
"""Import the agent sessions already on this machine, so the vault is useful on day one.

Reads Claude Code (`~/.claude/projects/*/*.jsonl`) and Codex (`~/.codex/sessions/YYYY/MM/DD/*.jsonl`) transcripts
and writes one page per session and day under `05 时间日志/会话摘录/`, named after the session's title (or its first
question): what you asked and the agent's closing answer, turn by turn. Tool calls, tool output, thinking, injected
context and headless runs (`claude -p`, `codex exec`, the nightly job itself) are dropped; every line goes through
`redact()` first, so a key that once scrolled past in a session prints as `<redacted>`.

Local by default: nothing leaves the machine, no model is called. `--distill` sends each session's excerpt (already
redacted) to the nightly model lane and puts "what was decided / what changed" at the top of its page — that line is
what an agent's question lands on. `--dry-run` says how many characters that would send before anything is sent.

A page this script did not write is never touched (`source: krouter-import` in its frontmatter marks ours). Re-running
rewrites only our pages, so the excerpt follows the transcript; a page already distilled keeps its digest until the
session grows. `--consent` records your yes for the nightly job, which then imports yesterday on its own; `--revoke`
takes it back. The nightly job imports nothing without that yes.

Env: `KROUTER_CLAUDE_PROJECTS`, `KROUTER_CODEX_SESSIONS` point at other transcript roots (tests, other machines).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zones  # noqa: E402
from krouter_home import vault_path  # noqa: E402
from krouter_redact import redact  # noqa: E402

FOLDER = "05 时间日志/会话摘录"
MARK = "krouter-import"
ASK_MAX = 600        # 每条提问最多保留的字数
ANSWER_MAX = 900     # 每条回答最多保留的字数
PAGE_MAX = 40_000    # 一页（一个会话的一天）的摘录上限
DISTILL_MAX = 24_000
DISTILL_MIN_TURNS = 2
DISTILL_SESSIONS = 40  # 一次最多提炼多少个会话（最新的优先）
# 注入的上下文、命令回显、系统提醒：不是用户说的话
NOISE = re.compile(r"^\s*(<(environment_context|user_instructions|system-reminder|command-|local-command|"
                   r"task-notification|turn_aborted|permissions)|# AGENTS\.md|Caveat: The messages below|"
                   r"This session is being continued)", re.I)
TAGS = re.compile(r"<(system-reminder|ide_selection|ide_opened_file)>.*?</\1>", re.S)
UNSAFE = re.compile(r"[\\/:*?\"<>|#^\[\]\n\r\t]+")


def state_file() -> Path:
    base = Path(os.environ.get("KROUTER_STATE_DIR") or Path.home() / ".local/state/krouter")
    return base / "import.json"


def load_state() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(data: dict) -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def roots() -> dict[str, Path]:
    home = Path.home()
    return {"claude-code": Path(os.environ.get("KROUTER_CLAUDE_PROJECTS") or home / ".claude/projects"),
            "codex": Path(os.environ.get("KROUTER_CODEX_SESSIONS") or home / ".codex/sessions")}


def _dt(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def local_day(ts: str) -> date | None:
    dt = _dt(ts)
    return dt.date() if dt else None


def local_hm(ts: str) -> str:
    dt = _dt(ts)
    return dt.strftime("%H:%M") if dt else "--:--"


def clean(text: str, limit: int) -> str:
    text = TAGS.sub("", text or "").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = redact(text)
    if len(text) > limit:
        text = text[:limit].rstrip() + " …"
    return text


def _texts(content, kinds: tuple[str, ...]) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") in kinds]
    return []


def _lines(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    yield d
    except OSError:
        return


def read_claude(path: Path) -> dict:
    """{turns: [{ts, ask, answer}], cwd, title, id} of one Claude Code transcript; empty turns for a headless run."""
    s = {"turns": [], "cwd": "", "title": "", "id": path.stem}
    for d in _lines(path):
        if d.get("type") == "custom-title" and d.get("customTitle"):
            s["title"] = str(d["customTitle"])
            continue
        if d.get("isSidechain") or d.get("isMeta") or d.get("isCompactSummary"):
            continue
        if str(d.get("entrypoint") or "").startswith("sdk-"):
            return {**s, "turns": []}  # 无头调用（夜间任务、脚本里的 claude -p）：是自动化，不是你说的话
        origin = d.get("origin")
        if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
            continue  # 后台任务通知之类
        s["cwd"] = d.get("cwd") or s["cwd"]
        msg = d.get("message") or {}
        if d.get("type") == "user":
            asks = [t for t in _texts(msg.get("content"), ("text",)) if t.strip() and not NOISE.match(t)]
            if asks:
                s["turns"].append({"ts": d.get("timestamp", ""), "ask": "\n".join(asks), "answer": ""})
        elif d.get("type") == "assistant" and s["turns"]:
            said = [t for t in _texts(msg.get("content"), ("text",)) if t.strip()]
            if said:
                s["turns"][-1]["answer"] = said[-1]  # 这一轮最后说的那段，通常是结论
    return s


def read_codex(path: Path) -> dict:
    s = {"turns": [], "cwd": "", "title": "", "id": path.stem}
    for d in _lines(path):
        p = d.get("payload")
        if not isinstance(p, dict):
            continue
        if d.get("type") == "session_meta":
            s["cwd"] = p.get("cwd") or s["cwd"]
            s["id"] = str(p.get("id") or s["id"])
            if "exec" in str(p.get("originator") or ""):
                return {**s, "turns": []}  # codex exec：无头自动化
            continue
        if d.get("type") != "response_item" or p.get("type") != "message":
            continue
        if p.get("role") == "user":
            asks = [t for t in _texts(p.get("content"), ("input_text",)) if t.strip() and not NOISE.match(t)]
            if asks:
                s["turns"].append({"ts": d.get("timestamp", ""), "ask": "\n".join(asks), "answer": ""})
        elif p.get("role") == "assistant" and s["turns"]:
            said = [t for t in _texts(p.get("content"), ("output_text",)) if t.strip()]
            if said:
                s["turns"][-1]["answer"] = said[-1]
    return s


def transcripts(since: date) -> list[tuple[str, Path]]:
    """Transcript files touched on or after `since` (mtime), oldest first."""
    cut = datetime.combine(since, datetime.min.time()).timestamp()
    found: list[tuple[float, str, Path]] = []
    for agent, root in roots().items():
        if not root.is_dir():
            continue
        for path in root.rglob("*.jsonl"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cut and "subagents" not in path.parts:
                found.append((mtime, agent, path))
    return [(a, p) for _, a, p in sorted(found)]


def agent_of(path: Path) -> str:
    """Which agent wrote a transcript, from where it lives (or, failing that, its first lines)."""
    for agent, root in roots().items():
        try:
            path.resolve().relative_to(root.resolve())
            return agent
        except ValueError:
            pass
    return "codex" if path.name.startswith("rollout-") else "claude-code"


def collect(since: date, until: date, files: list[Path] | None = None) -> list[dict]:
    """One entry per (session, local day): {agent, id, day, project, title, turns}."""
    out: list[dict] = []
    for agent, path in ([(agent_of(f), f) for f in files] if files else transcripts(since)):
        s = read_claude(path) if agent == "claude-code" else read_codex(path)
        by_day: dict[date, list[dict]] = defaultdict(list)
        for t in s["turns"]:
            day = local_day(t["ts"])
            if day and since <= day <= until:
                by_day[day].append(t)
        for day, turns in by_day.items():
            out.append({"agent": agent, "id": s["id"], "day": day, "turns": turns,
                        "project": Path(s["cwd"]).name if s["cwd"] else "",
                        "title": s["title"] or clean(turns[0]["ask"], 60).split("\n")[0]})
    out.sort(key=lambda e: (e["day"], e["turns"][0]["ts"]))
    return out


def file_name(e: dict) -> str:
    title = UNSAFE.sub(" ", e["title"]).strip(" .") or "会话"
    return f"{e['day'].isoformat()}｜{title[:40].strip()}（{e['id'][:8]}）.md"


def frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")[:800].replace("\r\n", "\n")
    except OSError:
        return {}
    if not text.startswith("---\n"):
        return {}
    meta = {}
    for line in text[4:].split("\n---", 1)[0].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def existing(folder: Path) -> dict[tuple[str, str], Path]:
    """Our pages by (session id, day), so a renamed session replaces its old page instead of adding one."""
    found: dict[tuple[str, str], Path] = {}
    if folder.is_dir():
        for path in folder.glob("*.md"):
            meta = frontmatter(path)
            if meta.get("source") == MARK and meta.get("session"):
                found[(meta["session"], meta.get("date", ""))] = path
    return found


def old_digest(path: Path | None, turns: int) -> str:
    """Keep a digest already made for this page unless the session has grown since."""
    if not path or not path.is_file():
        return ""
    meta = frontmatter(path)
    if meta.get("digest_turns") != str(turns):
        return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"\n## 定了什么、改了什么（模型提炼，待你确认）\n\n(.*?)\n\n## ", text, re.S)
    return m.group(1).strip() if m else ""


def render(e: dict, digest: str = "") -> str:
    turns = e["turns"]
    meta = ["---", "type: session-excerpt", f"source: {MARK}", "status: imported", f"date: {e['day'].isoformat()}",
            f"agent: {e['agent']}", f"session: {e['id']}", f"project: {e['project'] or '-'}", f"turns: {len(turns)}"]
    title = clean(e["title"], 80).replace("\n", " ")
    meta.append(f"title: {title}")
    if digest:
        meta.append(f"digest_turns: {len(turns)}")
        first = re.sub(r"^[-*]\s*", "", digest.strip().splitlines()[0])
        meta.append(f"how: {first}")  # 召回命中这页时先给的那一句：这段会话定下来的第一件事
    else:
        meta.append(f"how: 会话摘录（{len(turns)} 轮，还没提炼）：{title}")
    out = meta + ["---", "", f"# {title}", ""]
    if digest:
        out += ["## 定了什么、改了什么（模型提炼，待你确认）", "", digest.strip(), ""]
    out += [f"## 摘录（{e['day'].isoformat()} · {e['project'] or '?'} · {e['agent']} · {len(turns)} 轮）", "",
            "只留你的提问和每轮最后的回答，已脱敏。这是线索，不是结论：定下来的规则写进规则页。", ""]
    size = sum(len(x) for x in out)
    for i, t in enumerate(turns):
        if size > PAGE_MAX:
            out.append(f"- （还有 {len(turns) - i} 轮，超出一页的摘录上限，未展开）")
            break
        block = [f"- **问**（{local_hm(t['ts'])}）：" + clean(t["ask"], ASK_MAX).replace("\n", "\n  ")]
        if t["answer"]:
            block.append("  **答**：" + clean(t["answer"], ANSWER_MAX).replace("\n", "\n  "))
        out += block
        size += sum(len(b) for b in block)
    return "\n".join(out).rstrip() + "\n"


DISTILL_PROMPT = """下面是一个人和他的编程 agent 在 {day} 的一段会话摘录（项目：{project}；只有提问和每轮最后的回答，已脱敏）。

只做一件事：列出这段会话里**定下来的事**和**改主意的事**，每条一行，最多 8 条。
- 定下来的事：一个决定、一条规则、一个做法，写成能直接照做的一句话（例：「发版只从 main 打 tag」）。
- 改主意的事：先定了 A，后来改成 B，写成「原来 A → 改成 B」。
- 每条行尾用括号标出处：那一轮提问的时间，例如（14:05）。
- 只写摘录里明确出现的内容，不推测、不补充；没有就只回一行「- （这段会话没有定下来的事）」。
- 输出纯 Markdown 列表，不要前言和总结。

摘录：

{text}
"""


def distill(e: dict, page: str, vault: Path, dry: bool) -> tuple[str, int]:
    body = page.split("\n## 摘录", 1)[-1][:DISTILL_MAX]
    prompt = DISTILL_PROMPT.format(day=e["day"].isoformat(), project=e["project"] or "?", text=body)
    if dry:
        return "", len(prompt)
    import llm

    text = llm.complete(prompt, vault)
    lines = [ln.rstrip() for ln in redact(text).splitlines() if ln.strip().startswith(("-", "*"))]
    return "\n".join(lines[:8]), len(prompt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default=vault_path())
    ap.add_argument("--days", type=int, default=7, help="how many days back, today included (default 7)")
    ap.add_argument("--yesterday", action="store_true", help="only yesterday (what the nightly job runs)")
    ap.add_argument("--distill", action="store_true", help="also ask the model lane what each session decided")
    ap.add_argument("--dry-run", action="store_true", help="write nothing, send nothing: say what would happen")
    ap.add_argument("--consent", action="store_true", help="record your yes for the nightly job, then import")
    ap.add_argument("--revoke", action="store_true", help="the nightly job stops importing")
    ap.add_argument("--nightly", action="store_true", help="run only when consent was given (used by nightly.py)")
    ap.add_argument("--file", action="append", default=[], help="import this transcript only, all its days "
                    "(the session-end hook); runs only when consent was given")
    ap.add_argument("--distill-max", type=int, default=DISTILL_SESSIONS, help="distill at most this many sessions, newest first")
    ap.add_argument("--cli", default="", help=argparse.SUPPRESS)
    ap.add_argument("--model", default="", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.cli:
        os.environ["KROUTER_LEARN_CLI"] = args.cli
    if args.model:
        os.environ["KROUTER_LEARN_MODEL"] = args.model
    if args.revoke:
        save_state({**load_state(), "consent": False})
        print(json.dumps({"import": "revoked"}))
        return 0
    if not args.vault:
        print("set OBSIDIAN_VAULT", file=sys.stderr)
        return 2
    vault = Path(args.vault).expanduser()
    st = load_state()
    if (args.nightly or args.file) and not st.get("consent"):
        print(json.dumps({"import": "off", "reason": "no consent yet (import_sessions.py --consent)",
                          "chars": 0, "writes": []}))
        return 0
    distill_on = args.distill or bool((args.nightly or args.file) and st.get("distill"))
    today = date.today()
    if args.yesterday or args.nightly:
        since = until = today - timedelta(days=1)
    else:
        since, until = today - timedelta(days=max(args.days, 1) - 1), today
    files = [Path(f).expanduser() for f in args.file if Path(f).expanduser().is_file()]
    if args.file:
        since, until = date(1970, 1, 1), today
        if not files:
            print(json.dumps({"import": "skipped", "reason": "transcript not found", "chars": 0, "writes": []}))
            return 0
    entries = collect(since, until, files or None)
    folder = zones.path(vault, FOLDER)
    have = existing(folder)
    to_distill = {id(e) for e in sorted((e for e in entries if len(e["turns"]) >= DISTILL_MIN_TURNS),
                                        key=lambda e: e["turns"][-1]["ts"], reverse=True)[:max(args.distill_max, 0)]}
    written, kept, sent, calls, failed = [], [], 0, 0, 0
    for e in entries:
        target = folder / file_name(e)
        if target.exists() and frontmatter(target).get("source") != MARK:
            kept.append(target.name)
            continue
        before = have.get((e["id"], e["day"].isoformat()))
        page = render(e)
        digest = old_digest(before, len(e["turns"]))
        if not digest and distill_on and id(e) in to_distill:
            try:
                digest, n = distill(e, page, vault, args.dry_run)
                sent += n
                calls += 1
            except Exception as exc:  # noqa: BLE001  模型失败不影响本地摘录
                failed += 1
                print(f"distill {target.name}: {str(exc)[:200]}", file=sys.stderr)
        if digest:
            page = render(e, digest)
        if not args.dry_run:
            folder.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_text(page, encoding="utf-8")
            os.replace(tmp, target)
            if before and before != target and before.exists():
                before.unlink()  # 会话改了标题：换成新文件名，不留两份
        written.append(zones.canon(vault, str(target.relative_to(vault)).replace(os.sep, "/")))
    if args.consent and not args.dry_run:
        save_state({**st, "consent": True, "distill": bool(args.distill),
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    row = {"import": "dry-run" if args.dry_run else "done", "from": since.isoformat(), "through": until.isoformat(),
           "sessions": len({e["id"] for e in entries}), "pages": len(entries),
           "turns": sum(len(e["turns"]) for e in entries), "agents": sorted({e["agent"] for e in entries}),
           "distilled": calls, "distill_failed": failed, "chars": sent,
           "writes": written if len(written) <= 20 else written[:20] + [f"… {len(written) - 20} more"],
           "kept_foreign": kept}
    print(json.dumps(row, ensure_ascii=False))
    return 1 if failed and not calls else 0


if __name__ == "__main__":
    raise SystemExit(main())
