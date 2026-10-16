"""A new session must not start from an answer the user already changed.

The SessionStart hook brings this repository's recorded decisions. When a later correction says "原来 A → 改成 B",
the older line "A" is left out (it used to be injected next to the correction, so the agent saw both). A line that
restates the new decision, and unrelated decisions, stay. Chains (A → B, then B → C) keep only the newest.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / "skill/krouter-obsidian/scripts/session_hook.py"


@pytest.fixture()
def world(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    root = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                          check=True).stdout.strip()
    vault = tmp_path / "vault"
    (vault / "05 时间日志/会话摘录").mkdir(parents=True)
    state = tmp_path / "state"
    state.mkdir()
    (state / "import.json").write_text('{"consent": true}', encoding="utf-8")

    def page(name: str, days_ago: int, lines: list[str], status: str = "active") -> None:
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        body = "\n".join(f"- {ln}" for ln in lines)
        (vault / "05 时间日志/会话摘录" / f"{name}.md").write_text(
            f"---\ntype: session-excerpt\nsource: krouter-import\nstatus: {status}\ndate: {day}\nproject_root: {root}\n---\n\n"
            f"# {name}\n\n## 定了什么、改了什么（模型提炼，待你确认）\n\n{body}\n", encoding="utf-8")

    def inject() -> str:
        env = {**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_STATE_DIR": str(state)}
        res = subprocess.run([sys.executable, str(HOOK), "start"], input=json.dumps({"cwd": str(repo)}), env=env,
                             capture_output=True, text=True, timeout=60)
        out = res.stdout.strip()
        return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""

    return page, inject


def test_a_replaced_decision_is_not_injected(world):
    page, inject = world
    page("s1", 10, ["本地 API 端口用 8080（10:05）", "日志级别用 info（10:20）"])
    page("s2", 3, ["原来本地 API 端口 8080 → 改成 9090（14:00）"])
    ctx = inject()
    assert "→ 改成 9090" in ctx and "日志级别用 info" in ctx
    assert "本地 API 端口用 8080" not in ctx


def test_a_line_that_restates_the_new_decision_stays(world):
    page, inject = world
    page("s1", 10, ["原来本地 API 端口 8080 → 改成 9090（14:00）"])
    page("s2", 2, ["本地 API 端口用 9090，已经写进 README（09:00）"])
    assert "本地 API 端口用 9090" in inject()


def test_same_page_decide_then_change(world):
    page, inject = world
    page("s1", 1, ["发版从任意分支打 tag（10:00）", "原来发版从任意分支打 tag → 改成只从 main 打 tag（11:30）"])
    ctx = inject()
    assert "只从 main 打 tag" in ctx and "- 发版从任意分支打 tag（10:00）" not in ctx


def test_a_chain_keeps_only_the_newest(world):
    page, inject = world
    page("s1", 9, ["原来缓存过期 30 分钟 → 改成 10 分钟（10:00）"])
    page("s2", 2, ["原来缓存过期 10 分钟 → 改成 5 分钟（15:00）"])
    ctx = inject()
    assert "改成 5 分钟" in ctx and "改成 10 分钟" not in ctx


def test_english_lines(world):
    page, inject = world
    page("s1", 8, ["Releases ship from any branch, tagged by hand (10:05)"])
    page("s2", 1, ["was releases ship from any branch → now releases ship from main only, tagged by CI (16:40)"])
    ctx = inject()
    assert "main only" in ctx and "- Releases ship from any branch, tagged by hand" not in ctx
