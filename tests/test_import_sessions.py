"""Day-one value: agent sessions already on the machine become vault pages — local, redacted, never someone's own page."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skill/krouter-obsidian/scripts"
IMPORT = SCRIPTS / "import_sessions.py"
FOLDER = "05 时间日志/会话摘录"
KEY = "sk-" + "Abc123XyZ" * 4


def _ts(days_ago: int, hour: int = 10) -> str:
    day = datetime.now().astimezone() - timedelta(days=days_ago)
    return day.replace(hour=hour, minute=5, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def _claude_session(root: Path, name: str, days_ago: int, entry: str = "claude-desktop", title: str = "") -> Path:
    ts = _ts(days_ago)
    rows = [
        {"type": "user", "entrypoint": entry, "cwd": "/work/shop", "timestamp": ts, "origin": {"kind": "human"},
         "message": {"role": "user", "content": "发版流程怎么定？key 是 " + KEY}},
        {"type": "user", "entrypoint": entry, "timestamp": ts, "isMeta": True,
         "message": {"role": "user", "content": "<command-name>/clear</command-name>"}},
        {"type": "assistant", "entrypoint": entry, "timestamp": ts,
         "message": {"content": [{"type": "thinking", "thinking": "secret plan"}, {"type": "tool_use", "name": "Bash"}]}},
        {"type": "user", "entrypoint": entry, "timestamp": ts,
         "message": {"content": [{"type": "tool_result", "content": "tool output here"}]}},
        {"type": "assistant", "entrypoint": entry, "timestamp": ts,
         "message": {"content": [{"type": "text", "text": "定了：发版只从 main 打 tag。"}]}},
        {"type": "user", "entrypoint": entry, "timestamp": ts, "isSidechain": True,
         "message": {"role": "user", "content": "subagent prompt"}},
        {"type": "user", "entrypoint": entry, "timestamp": ts, "origin": {"kind": "task-notification"},
         "message": {"role": "user", "content": "background task finished"}},
    ]
    if title:
        rows.append({"type": "custom-title", "customTitle": title})
    return _jsonl(root / "-work-shop" / f"{name}.jsonl", rows)


def _codex_session(root: Path, days_ago: int, originator: str = "codex_cli_rs") -> Path:
    ts = _ts(days_ago, 15)
    day = datetime.now().astimezone() - timedelta(days=days_ago)
    rows = [
        {"type": "session_meta", "timestamp": ts, "payload": {"id": "019a-codex-0001", "cwd": "/work/api", "originator": originator}},
        {"type": "response_item", "timestamp": ts, "payload": {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "<environment_context>cwd</environment_context>"},
            {"type": "input_text", "text": "缓存过期时间改成多少？"}]}},
        {"type": "response_item", "timestamp": ts, "payload": {"type": "function_call", "name": "shell"}},
        {"type": "response_item", "timestamp": ts, "payload": {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "原来 30 分钟，改成 10 分钟。"}]}},
    ]
    return _jsonl(root / day.strftime("%Y/%m/%d") / f"rollout-{originator}.jsonl", rows)


@pytest.fixture()
def env(tmp_path):
    vault = tmp_path / "vault"
    (vault / "05 时间日志").mkdir(parents=True)
    claude, codex = tmp_path / "claude", tmp_path / "codex"
    e = {**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_CLAUDE_PROJECTS": str(claude),
         "KROUTER_CODEX_SESSIONS": str(codex), "KROUTER_STATE_DIR": str(tmp_path / "state"), "KROUTER_NO_QUERY_LOG": "1"}
    return {"vault": vault, "claude": claude, "codex": codex, "env": e}


def _run(env: dict, *args: str) -> dict:
    res = subprocess.run([sys.executable, str(IMPORT), *args], env=env["env"], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
    return json.loads(res.stdout.strip().splitlines()[-1])


def _pages(env: dict) -> dict[str, str]:
    folder = env["vault"] / FOLDER
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.md"))} if folder.is_dir() else {}


def test_import_keeps_asks_and_closing_answers_only_and_redacts(env):
    _claude_session(env["claude"], "aaaa1111-s", 1, title="发版流程")
    _codex_session(env["codex"], 2)
    _claude_session(env["claude"], "bbbb2222-headless", 1, entry="sdk-cli")  # 夜间任务自己的 claude -p
    _codex_session(env["codex"], 1, originator="codex_exec")
    out = _run(env, "--days", "7")
    assert out["pages"] == 2 and out["agents"] == ["claude-code", "codex"] and out["chars"] == 0
    pages = _pages(env)
    claude_page = next(v for k, v in pages.items() if "发版流程" in k)
    assert "source: krouter-import" in claude_page and "title: 发版流程" in claude_page
    assert "发版流程怎么定" in claude_page and "定了：发版只从 main 打 tag。" in claude_page
    assert KEY not in claude_page and "<redacted>" in claude_page
    for noise in ("secret plan", "tool output here", "subagent prompt", "background task", "/clear"):
        assert noise not in claude_page
    codex_page = next(v for k, v in pages.items() if "缓存过期" in k)
    assert "原来 30 分钟，改成 10 分钟。" in codex_page and "environment_context" not in codex_page


def test_dry_run_writes_nothing_and_foreign_pages_are_never_touched(env):
    _claude_session(env["claude"], "aaaa1111-s", 1, title="发版流程")
    out = _run(env, "--dry-run")
    assert out["import"] == "dry-run" and out["pages"] == 1 and not (env["vault"] / FOLDER).exists()
    _run(env)
    name = next(iter(_pages(env)))
    mine = env["vault"] / FOLDER / name
    mine.write_text("# my own notes\n", encoding="utf-8")  # 宿主把这页改成了自己的
    again = _run(env)
    assert again["kept_foreign"] == [name] and mine.read_text(encoding="utf-8") == "# my own notes\n"


def test_renamed_session_replaces_its_page(env):
    path = _claude_session(env["claude"], "aaaa1111-s", 1)
    _run(env)
    assert len(_pages(env)) == 1
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "custom-title", "customTitle": "新标题"}, ensure_ascii=False) + "\n")
    _run(env)
    names = list(_pages(env))
    assert len(names) == 1 and "新标题" in names[0]


def test_nightly_imports_only_after_consent(env):
    _claude_session(env["claude"], "aaaa1111-s", 1, title="昨天")
    off = _run(env, "--nightly")
    assert off["import"] == "off" and not _pages(env)
    _run(env, "--consent", "--dry-run")  # dry-run 不记同意
    assert _run(env, "--nightly")["import"] == "off"
    _run(env, "--consent", "--days", "1")
    on = _run(env, "--nightly")
    assert on["import"] == "done" and on["pages"] == 1
    _run(env, "--revoke")
    assert _run(env, "--nightly")["import"] == "off"


def test_distill_puts_decisions_on_top_and_keeps_them(env, monkeypatch):
    path = _claude_session(env["claude"], "aaaa1111-s", 1, title="发版流程")
    ts = _ts(1, 11)
    with path.open("a", encoding="utf-8") as fh:  # 一轮的会话不提炼：至少两轮
        fh.write(json.dumps({"type": "user", "timestamp": ts, "message": {"role": "user", "content": "那就这么定"}}) + "\n")
    sys.path.insert(0, str(SCRIPTS))
    import import_sessions as imp
    import llm

    sent = []
    monkeypatch.setattr(llm, "complete", lambda prompt, vault=None: sent.append(prompt) or
                        "好的：\n- 发版只从 main 打 tag（10:05）\n- 原来手动发 → 改成 CI 发（10:05）\n总结完毕")
    for k in ("OBSIDIAN_VAULT", "KROUTER_CLAUDE_PROJECTS", "KROUTER_CODEX_SESSIONS", "KROUTER_STATE_DIR"):
        monkeypatch.setenv(k, env["env"][k])
    monkeypatch.setattr(sys, "argv", ["import_sessions.py", "--distill"])
    assert imp.main() == 0
    page = next(iter(_pages(env).values()))
    assert len(sent) == 1 and KEY not in sent[0]  # 发出去的也是脱敏后的
    assert "## 定了什么、改了什么" in page and "- 发版只从 main 打 tag（10:05）" in page and "总结完毕" not in page
    assert "how: 发版只从 main 打 tag（10:05）" in page
    monkeypatch.setattr(sys, "argv", ["import_sessions.py", "--distill"])
    assert imp.main() == 0 and len(sent) == 1  # 会话没变：不重复提炼，也不丢掉已有的提炼


def test_imported_page_answers_a_question_through_the_router(env, tmp_path):
    vault = env["vault"]
    import shutil

    shutil.rmtree(vault)
    shutil.copytree(REPO / "template-zh", vault)
    _claude_session(env["claude"], "aaaa1111-s", 1, title="发版流程")
    _run(env)
    res = subprocess.run([sys.executable, str(SCRIPTS / "route_knowledge.py"), "search", "发版只从 main 打 tag 吗"],
                         env={**env["env"], "KROUTER_CACHE_DIR": str(tmp_path / "cache")},
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    assert "05 时间日志/会话摘录/" in res.stdout.split("recall:", 1)[1].splitlines()[1]
