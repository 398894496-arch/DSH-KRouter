"""A key pasted into the vault never leaves through KRouter: not to a model, not into an agent's context,
not into the query log or the recall cache."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skill/krouter-obsidian/scripts"
FAKE = "sk-FAKEFAKEFAKE1234567890abcdef"
KEY_PAGE = "90 系统文件/自动化/自进化钥匙.md"
OTHER = "90 系统文件/Agent记忆/DeepSeek 凭据.md"


@pytest.fixture()
def keyed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    shutil.copytree(REPO / "template", vault)
    page = vault / KEY_PAGE
    # what the page tells a host to do: uncomment one line and paste the key
    page.write_text(re.sub(r"^# (DEEPSEEK_API_KEY=).*$", r"\g<1>" + FAKE, page.read_text(encoding="utf-8"),
                           count=1, flags=re.M), encoding="utf-8")
    (vault / OTHER).write_text("---\ntitle: DeepSeek 凭据\nstatus: active\n---\n\n# DeepSeek 凭据\n\n"
                               f"脚本读环境变量 DEEPSEEK_API_KEY。\nDEEPSEEK_API_KEY={FAKE}\n", encoding="utf-8")
    return vault


def test_redact_keeps_placeholders_and_numbers():
    sys.path.insert(0, str(SCRIPTS))
    from krouter_redact import redact

    assert FAKE not in redact(f"DEEPSEEK_API_KEY={FAKE}")
    assert redact("# DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY") == "# DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY"
    assert redact("tokens: 158386") == "tokens: 158386" and redact("max_tokens=8000") == "max_tokens=8000"
    assert "abcdefghijklmnopqrstu" not in redact("Authorization: Bearer abcdefghijklmnopqrstu12345")
    assert "ghp_" not in redact("用 ghp_ABCDEFGHIJKLMNOPQRSTUVWX12 推送")


def test_cards_and_topics_never_send_a_key(keyed_vault, monkeypatch, tmp_path):
    monkeypatch.setenv("KROUTER_CACHE_DIR", str(tmp_path / "cache"))
    import answer_cards as ac
    import consolidate_topics as ct
    import llm

    sent: list[str] = []

    def capture(prompt, v=None):
        sent.append(prompt)
        return "{}"

    monkeypatch.setattr(llm, "complete", capture)
    monkeypatch.setattr("sys.argv", ["answer_cards.py", "--vault", str(keyed_vault), "--jobs", "1"])
    assert ac.main() == 0
    assert sent, "answer cards sent nothing at all"
    assert KEY_PAGE not in ac.targets(keyed_vault)  # the key page is never a card target
    assert not any(FAKE in p for p in sent)
    assert any(OTHER in p for p in sent)  # the other page still goes, with its key redacted
    evidence, sources, _ = ct.gather(keyed_vault, {"slug": "k", "title": "密钥", "terms": ["DEEPSEEK_API_KEY"], "auth": []})
    assert FAKE not in evidence and KEY_PAGE not in sources


@pytest.mark.skipif(os.name == "nt", reason="POSIX router")
@pytest.mark.parametrize("sh_only", ["0", "1"])
def test_router_never_prints_or_logs_a_key(keyed_vault, tmp_path, sh_only):
    state, cache = tmp_path / "state", tmp_path / "cache"
    env = {**os.environ, "OBSIDIAN_VAULT": str(keyed_vault), "KROUTER_SH_ONLY": sh_only, "KROUTER_STATE_DIR": str(state),
           "KROUTER_CACHE_DIR": str(cache), "KROUTER_NO_QUERY_LOG": "0"}
    for route, q in (("search", "DEEPSEEK API key 怎么填"), ("search", "DEEPSEEK_API_KEY"), ("memory", "DeepSeek 凭据"),
                     ("search", f"我的 key 是 {FAKE}")):
        out = subprocess.run(["/bin/sh", str(SCRIPTS / "route_knowledge.sh"), route, q], env=env,
                             capture_output=True, text=True, timeout=60)
        assert FAKE not in out.stdout.replace(q, ""), (route, q)
    log = state / "queries.jsonl"
    if log.is_file():
        assert FAKE not in log.read_text(encoding="utf-8")
    for db in cache.rglob("*.sqlite*"):
        assert FAKE.encode() not in db.read_bytes()


def test_upgrade_rebuilds_a_cache_built_before_redaction(keyed_vault, tmp_path, monkeypatch):
    """A cache written by an older version holds raw page text; the schema bump must force a full rebuild."""
    monkeypatch.setenv("KROUTER_CACHE_DIR", str(tmp_path / "cache"))
    import recall_index as ri

    con = ri.connect(ri.cache_path(keyed_vault))
    ri.refresh(keyed_vault, con)
    # simulate the old cache: same files, raw (unredacted) body, older schema tag
    con.execute("UPDATE docs SET body = body || ' ' || ?", (FAKE,))
    con.execute("UPDATE meta SET v='recall-v11' WHERE k='schema'")
    con.commit()
    con.close()
    con = ri.connect(ri.cache_path(keyed_vault))
    ri.refresh(keyed_vault, con)
    assert not any(FAKE in (b or "") for (b,) in con.execute("SELECT body FROM docs"))
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    for db in (tmp_path / "cache").rglob("*.sqlite*"):
        assert FAKE.encode() not in db.read_bytes(), db  # not left behind in free pages either
