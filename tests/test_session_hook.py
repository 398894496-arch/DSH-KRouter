"""Claude Code hooks: a new session gets this project's recorded decisions; an ended one is imported. Both only after
the host said yes to importing."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "skill/krouter-obsidian/scripts/session_hook.py"


def _setup(tmp_path: Path, consent: bool = True) -> dict:
    vault = tmp_path / "vault"
    shutil.copytree(REPO / "template", vault)
    folder = vault / "05 时间日志/会话摘录"
    folder.mkdir(parents=True)
    today = date.today().isoformat()
    (folder / f"{today}｜发版（aaaa1111）.md").write_text(
        f"---\nsource: krouter-import\nstatus: imported\ndate: {today}\nproject: shop\ndigest_turns: 4\n---\n\n# 发版\n\n"
        "## 定了什么、改了什么（模型提炼，待你确认）\n\n- 发版只从 main 打 tag（10:05）\n- 原来手动上传 → 改成 CI 发布（10:20）\n\n"
        "## 摘录\n\n- **问**：…\n", encoding="utf-8")
    (folder / "2020-01-01｜旧事（bbbb2222）.md").write_text(
        "---\nsource: krouter-import\ndate: 2020-01-01\nproject: shop\n---\n\n## 定了什么、改了什么（模型提炼，待你确认）\n\n"
        "- 很久以前的决定\n\n## 摘录\n", encoding="utf-8")
    (folder / f"{today}｜别的项目（cccc3333）.md").write_text(
        f"---\nsource: krouter-import\ndate: {today}\nproject: other\n---\n\n## 定了什么、改了什么（模型提炼，待你确认）\n\n"
        "- 别的项目的决定\n\n## 摘录\n", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    if consent:
        (state / "import.json").write_text(json.dumps({"consent": True}), encoding="utf-8")
    env = {**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_STATE_DIR": str(state), "KROUTER_NO_QUERY_LOG": "1"}
    env.pop("KROUTER_INJECT", None)
    return {"vault": vault, "env": env, "state": state}


def _hook(env: dict, which: str, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK), which], input=json.dumps(payload), env=env,
                          capture_output=True, text=True, timeout=60)


def test_start_brings_this_projects_recent_decisions_with_their_page(tmp_path):
    s = _setup(tmp_path)
    res = _hook(s["env"], "start", {"cwd": "/work/shop", "session_id": "x"})
    assert res.returncode == 0, res.stderr
    ctx = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    lines = ctx.splitlines()
    assert "项目 shop" in lines[0]
    assert lines[1].startswith("- 原来手动上传 → 改成 CI 发布") and "05 时间日志/会话摘录/" in lines[1]  # 纠错在前
    assert "发版只从 main 打 tag" in ctx
    assert "很久以前的决定" not in ctx and "别的项目的决定" not in ctx  # 30 天外、别的项目：不带
    assert "krouter_ask" in lines[-1]


def test_start_is_silent_without_consent_without_decisions_or_when_turned_off(tmp_path):
    s = _setup(tmp_path, consent=False)
    assert _hook(s["env"], "start", {"cwd": "/work/shop"}).stdout == ""
    s = _setup(tmp_path / "b")
    assert _hook(s["env"], "start", {"cwd": "/work/no-such-project"}).stdout == ""
    assert _hook({**s["env"], "KROUTER_INJECT": "0"}, "start", {"cwd": "/work/shop"}).stdout == ""
    assert _hook(s["env"], "start", {}).returncode == 0
    bad = subprocess.run([sys.executable, str(HOOK), "start"], input="not json", env=s["env"], capture_output=True,
                         text=True, timeout=60)
    assert bad.returncode == 0  # hook 永远不让会话失败


def test_end_imports_the_session_that_just_ended(tmp_path):
    s = _setup(tmp_path)
    projects = tmp_path / "projects/-work-api"
    projects.mkdir(parents=True)
    ts = datetime.now(timezone.utc).isoformat()
    transcript = projects / "dddd4444-s.jsonl"
    transcript.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"type": "user", "timestamp": ts, "cwd": "/work/api", "message": {"role": "user", "content": "超时改成多少"}},
        {"type": "assistant", "timestamp": ts, "message": {"content": [{"type": "text", "text": "改成 10 秒。"}]}},
        {"type": "custom-title", "customTitle": "超时设置"}]) + "\n", encoding="utf-8")
    env = {**s["env"], "KROUTER_CLAUDE_PROJECTS": str(tmp_path / "projects")}
    res = _hook(env, "end", {"session_id": "dddd4444-s", "transcript_path": str(transcript), "cwd": "/work/api"})
    assert res.returncode == 0 and res.stdout == ""
    folder = s["vault"] / "05 时间日志/会话摘录"
    for _ in range(100):  # 导入在后台跑，不拖住 Claude Code
        if list(folder.glob("*超时设置*")):
            break
        time.sleep(0.1)
    page = next(folder.glob("*超时设置*")).read_text(encoding="utf-8")
    assert "project: api" in page and "改成 10 秒。" in page


def test_end_does_nothing_without_consent(tmp_path):
    s = _setup(tmp_path, consent=False)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    assert _hook(s["env"], "end", {"transcript_path": str(transcript)}).returncode == 0
    time.sleep(0.5)
    assert not (s["state"] / "session-hook.log").exists()


def test_plugin_declares_both_hooks():
    hooks = json.loads((REPO / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"SessionStart", "SessionEnd"}
    assert hooks["SessionStart"][0]["hooks"][0]["command"].endswith("session_hook.py\" start")
    assert hooks["SessionEnd"][0]["hooks"][0]["command"].endswith("session_hook.py\" end")
