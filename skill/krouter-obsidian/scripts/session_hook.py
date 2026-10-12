#!/usr/bin/env python3
"""Claude Code hooks: remember a session when it ends, bring this project's decisions when one starts.

The two things that make claude-mem feel like memory, done the KRouter way: what is captured is a plain Markdown
page you can read and fix, and what is brought back is a handful of decisions, each with the page it came from.

`session_hook.py end` (SessionEnd): imports the session that just ended (`import_sessions.py --file`), in the
background so Claude Code is not held up; it also distills that session when you said yes to distilling. Nothing
happens before you said yes to importing (`import_sessions.py --consent`, or the install's question).

`session_hook.py start` (SessionStart): prints, as context for the new session, up to 8 decisions recorded for this
repository (matched by its git top level, never by folder name) in the last 30 days, each naming its page,
corrections first. By default that is every line of pages you confirmed and only the corrections from the rest, marked
unconfirmed; `KROUTER_INJECT=all` brings every line, `KROUTER_INJECT=0` nothing. Nothing is printed when the vault
has none or the import was never turned on. In English unless the lines are Chinese. Reads only the vault; sends
nothing; well under a second.

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
from krouter_home import project_root, vault_path  # noqa: E402
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


CONFIRMED = {"active", "confirmed", "adopted"}
CJK = re.compile(r"[\u3400-\u9fff]")


def project_lines(vault: Path, root: str, everything: bool = False) -> list[tuple[str, str, bool]]:
    """[(line, page, confirmed)] for the project at `root`, corrections first, then newest first.

    A page counts only when its `project_root` is this repo: two repos that are both called `api` never share
    decisions. Pages from before 1.0.1 have no `project_root` and are left out until re-imported. From a page you
    confirmed (`status: active`, or `confirmed: true`) every line comes; from an unconfirmed one only corrections
    ("A → B"), unless `KROUTER_INJECT=all`."""
    if not root:
        return []
    cut = (date.today() - timedelta(days=DAYS)).isoformat()
    found: list[tuple[str, str, str, bool]] = []
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
            if meta.get("project_root") != root or (meta.get("date") and meta["date"] < cut):
                continue
            ok = meta.get("status", "").lower() in CONFIRMED or meta.get("confirmed", "").lower() == "true"
            rel = zones.canon(vault, str(page.relative_to(vault)).replace(os.sep, "/"))
            for ln in digest_lines(text):
                line = re.sub(r"^[-*]\s*", "", ln)
                if ok or everything or "→" in line:
                    found.append((meta.get("date") or "9999", line, rel, ok))
    found.sort(key=lambda x: x[0], reverse=True)
    seen, out = set(), []
    for _, line, rel, ok in sorted(found, key=lambda x: "→" not in x[1]):  # 稳定排序：纠错在前，其余仍按新到旧
        if line not in seen:
            seen.add(line)
            out.append((line, rel, ok))
    return out[:MAX_LINES]


HEAD = {
    "zh": ("KRouter：这个仓库（{name}）最近 {days} 天在你的库里记下的决定。「→」是改过的；"
           "标「待确认」的是模型提炼、用户还没确认的，只当线索："),
    "en": ("KRouter: decisions recorded in your vault for this repository ({name}) in the last {days} days. "
           "\"→\" marks a change of mind; lines marked (unconfirmed) were extracted by a model and not yet confirmed "
           "by the user, so treat them as clues:"),
}
TAIL = {"zh": "其他问题先用 krouter_ask 查库；库里没有（recall: none）就直说，不要猜。",
        "en": "For anything else, ask the vault with krouter_ask first; if it says recall: none, say so instead of guessing."}
MARK_UNCONFIRMED = {"zh": "（待确认）", "en": " (unconfirmed)"}


def start(payload: dict) -> int:
    mode = os.environ.get("KROUTER_INJECT", "")
    if mode == "0" or not consented():
        return 0
    raw = vault_path()
    if not raw or not Path(raw).is_dir():
        return 0
    root = project_root(payload.get("cwd") or os.getcwd())
    lines = project_lines(Path(raw), root, everything=mode == "all")
    if not lines:
        return 0
    lang = "zh" if any(CJK.search(line) for line, _, _ in lines) else "en"
    body = [HEAD[lang].format(name=Path(root).name, days=DAYS)]
    for line, rel, ok in lines:
        body.append(f"- {line}{'' if ok else MARK_UNCONFIRMED[lang]} 〔{rel}〕")
    body.append(TAIL[lang])
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
