"""One-step install for anyone: new vault from the right template, existing vaults never overwritten, re-run = upgrade."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOT = REPO / "scripts/bootstrap.py"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the POSIX path calls install.sh")


def _env(tmp: Path) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_BASE_URL", "_MODEL"))}
    env.update({"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8",
                "KROUTER_KEYS_ENV": str(tmp / "keys.env"), "KROUTER_WRITER": "/nonexistent/grok",
                "KROUTER_SKIP_LAUNCHD": "1", "KROUTER_SKIP_TIMER": "1"})
    for k in ("OBSIDIAN_VAULT", "KROUTER_SKILL_HOME", "KROUTER_CURSOR_RULE", "KROUTER_ASK_RULE", "KROUTER_LEARN_CLI"):
        env.pop(k, None)
    return env


def _boot(env: dict, *args: str) -> tuple[subprocess.CompletedProcess, dict]:
    res = subprocess.run([sys.executable, str(BOOT), "--no-open", *args], env=env, capture_output=True, text=True,
                         timeout=600)
    last = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "{}"
    return res, (json.loads(last) if last.startswith("{") else {})


def test_new_chinese_vault_then_upgrade_keeps_the_table(tmp_path):
    env = _env(tmp_path)
    vault = tmp_path / "home/Documents/第二大脑"
    res, out = _boot(env, "--lang", "zh")
    assert res.returncode == 0, res.stdout[-1500:] + res.stderr[-1500:]
    assert out["vault"] == str(vault) and out["state"] == "new" and out["lang"] == "zh"
    assert (vault / "02 经验与方法/自动化/按日志文件判断封账.md").is_file()  # the Chinese template
    table = vault / "90 系统文件/canonical_sources.psv"
    assert "按日志文件判断封账" in table.read_text(encoding="utf-8")  # its own sample table, not the English one
    assert (tmp_path / "home/.agents/skills/krouter-obsidian/scripts/route_knowledge.sh").is_file()
    assert "装好了" in res.stdout and "还没有可用的模型" in res.stdout  # plain-language next step, no model yet
    table.write_text(table.read_text(encoding="utf-8") + "Q99|我的名词|01 项目/项目.md|x\n", encoding="utf-8")
    res2, out2 = _boot(env, "--lang", "zh")
    assert res2.returncode == 0 and out2["state"] == "ours" and out2["added"] == 0
    assert "Q99|我的名词" in table.read_text(encoding="utf-8")


def test_existing_vault_only_gains_missing_files(tmp_path):
    env = _env(tmp_path)
    vault = tmp_path / "MyNotes"
    (vault / "Inbox").mkdir(parents=True)
    (vault / "Inbox/idea.md").write_text("# mine\n", encoding="utf-8")
    (vault / "Agent第二大脑.md").write_text("# my own home page\n", encoding="utf-8")
    res, out = _boot(env, "--lang", "en", "--vault", str(vault))
    assert res.returncode == 0, res.stderr[-1500:]
    assert out["state"] == "ours"  # it already has the home page name
    assert (vault / "Inbox/idea.md").read_text(encoding="utf-8") == "# mine\n"
    assert (vault / "Agent第二大脑.md").read_text(encoding="utf-8") == "# my own home page\n"  # never overwritten
    assert (vault / "90 系统文件/自动化/日更健康.md").is_file()  # the missing skeleton arrived


def test_dry_run_changes_nothing(tmp_path):
    env = _env(tmp_path)
    vault = tmp_path / "v"
    res, _ = _boot(env, "--lang", "en", "--vault", str(vault), "--dry-run")
    assert res.returncode == 0 and not vault.exists()
    assert not (tmp_path / "home/.agents").exists()


def test_chinese_template_alias_table_is_consistent():
    res = subprocess.run([sys.executable, str(REPO / "scripts/verify_canonical_map.py"), "--map",
                          str(REPO / "template-zh/90 系统文件/canonical_sources.psv"), "--vault", str(REPO / "template-zh")],
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0 and "failures=0" in res.stdout, res.stdout + res.stderr
