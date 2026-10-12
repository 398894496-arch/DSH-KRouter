#!/usr/bin/env python3
"""Claude Code hooks: remember a session when it ends, bring this project's decisions when one starts.

The two things that make claude-mem feel like memory, done the KRouter way: what is captured is a plain Markdown
page you can read and fix, and what is brought back is a handful of decisions, each with the page it came from.

`session_hook.py end` (SessionEnd): imports the session that just ended (`import_sessions.py --file`), in the
background so Claude Code is not held up; it also distills that session when you said yes to distilling. Nothing
happens before you said yes to importing (`import_sessions.py --consent`, or the install's question).

`session_hook.py start` (SessionStart): prints, as context for the new session, up to 8 decisions recorded for this
project in the last 30 days: the "what was decided" lines of distilled session pages, and decision pages imported from
claude-mem. Each line names its page. Corrections come first. Nothing is printed when the vault has none, when the
import was never turned on, or with `KROUTER_INJECT=0`. Reads only the vault; sends nothing; well under a second.

Both read the hook's JSON on stdin (`session_id`, `transcript_path`, `cwd`) and never fail the session.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import zones  # noqa: E402
from krouter_home import vault_path  # noqa: E402
from krouter_redact import redact  # noqa: E402

DAYS = 30
MAX_LINES = 8
MAX_CHARS = 1600
DIGEST_HEADS = ("## 定了什么、改了什么（模型提炼，待你确认）", "## 现在有效的、被取代的（模型整理，待你确认）")


def consented() -> bool:
    base = Path(os.environ.get("KROUTER_STATE_DIR") or Path.home() / ".local/state/krouter")
    for name in ("import.json", "import-claude-mem.json"):
        try:
            if json.loads((base / name).read_text(encoding="utf-8")).get("consent"):
                return True
        except (OSError, ValueError):
            continue
    return False


def meta_of(text: str) -> dict[str, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    out = {}
    for line in text[4:].split("\n---", 1)[0].splitlines():
        if ":" in line and not line.startswith((" ", "-")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def digest_lines(text: str) -> list[str]:
    for head in DIGEST_HEADS:
        if head in text:
            block = text.split(head, 1)[1].split("\n## ", 1)[0]
            return [ln.strip() for ln in block.splitlines() if ln.strip().startswith(("-", "*"))
                    and "没有定下来的事" not in ln]
    return []


def project_lines(vault: Path, project: str) -> list[tuple[str, str]]:
    """[(line, page)] for this project, newest first; corrections ("→") before the rest."""
    if not project:
        return []
    cut = (date.today() - timedelta(days=DAYS)).isoformat()
    found: list[tuple[str, str, str]] = []
    for folder in ("05 时间日志/会话摘录", "02 经验与方法/从 claude-mem 导入"):
        d = zones.path(vault, folder)
        if not d.is_dir():
            continue
        for page in d.glob("*.md"):
            try:
                text = page.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = meta_of(text)
            if meta.get("project") != project or (meta.get("date") and meta["date"] < cut):
                continue
            rel = zones.canon(vault, str(page.relative_to(vault)).replace(os.sep, "/"))
            for ln in digest_lines(text):
                found.append((meta.get("date") or "9999", re.sub(r"^[-*]\s*", "", ln), rel))
    found.sort(key=lambda x: x[0], reverse=True)
    seen, out = set(), []
    for _, line, rel in sorted(found, key=lambda x: "→" not in x[1]):  # 稳定排序：纠错在前，其余仍按新到旧
        if line not in seen:
            seen.add(line)
            out.append((line, rel))
    return out[:MAX_LINES]


def start(payload: dict) -> int:
    if os.environ.get("KROUTER_INJECT") == "0" or not consented():
        return 0
    raw = vault_path()
    if not raw or not Path(raw).is_dir():
        return 0
    project = Path(payload.get("cwd") or os.getcwd()).name
    lines = project_lines(Path(raw), project)
    if not lines:
        return 0
    body = [f"KRouter：项目 {project} 最近 {DAYS} 天在你的库里记下的决定（模型提炼，用户还没逐条确认；「→」是改过的）："]
    for line, rel in lines:
        body.append(f"- {line} 〔{rel}〕")
    body.append("其他问题先用 krouter_ask 查库；库里没有（recall: none）就直说，不要猜。")
    text = redact("\n".join(body))[:MAX_CHARS]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}},
                     ensure_ascii=False))
    return 0


def end(payload: dict) -> int:
    transcript = payload.get("transcript_path") or ""
    if not transcript or not consented():
        return 0
    raw = vault_path()
    if not raw:
        return 0
    log = Path(os.environ.get("KROUTER_STATE_DIR") or Path.home() / ".local/state/krouter") / "session-hook.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [sys.executable, str(HERE / "import_sessions.py"), "--vault", raw, "--file", transcript]
    with log.open("a", encoding="utf-8") as fh:
        kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": 0x00000008}  # DETACHED_PROCESS
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=fh, stderr=fh,
                         env={**os.environ, "OBSIDIAN_VAULT": raw}, **kw)
    return 0


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    try:
        return {"start": start, "end": end}.get(which, lambda p: 0)(payload if isinstance(payload, dict) else {})
    except Exception as exc:  # noqa: BLE001  hook 永远不能让会话失败
        print(f"krouter hook: {str(exc)[:200]}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
