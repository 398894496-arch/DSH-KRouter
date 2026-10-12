"""The MCP server speaks JSON-RPC over stdio and finds the vault the installer recorded, with no env var."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skill/krouter-obsidian/scripts"


def _talk(env: dict, *msgs: dict) -> list[dict]:
    data = "\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n"
    res = subprocess.run([sys.executable, str(SCRIPTS / "mcp_server.py")], input=data, env=env,
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    return [json.loads(line) for line in res.stdout.splitlines() if line.strip()]


def test_initialize_list_and_ask(tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(REPO / "template", vault)
    vault_file = tmp_path / "config/krouter/vault"
    vault_file.parent.mkdir(parents=True)
    vault_file.write_text(str(vault) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "OBSIDIAN_VAULT"}
    env.update({"KROUTER_VAULT_FILE": str(vault_file), "KROUTER_NO_QUERY_LOG": "1", "KROUTER_CACHE_DIR": str(tmp_path / "c")})
    replies = _talk(env,
                    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "krouter_ask", "arguments": {"query": "Agent second brain"}}},
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "krouter_ask", "arguments": {"query": "x", "route": "rm -rf"}}},
                    {"jsonrpc": "2.0", "id": 5, "method": "nope"})
    assert [r["id"] for r in replies] == [1, 2, 3, 4, 5]  # 通知不回
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18" and "recall: none" in replies[0]["result"]["instructions"]
    assert {t["name"] for t in replies[1]["result"]["tools"]} == {"krouter_ask", "krouter_status"}
    ask = replies[2]["result"]
    assert ask["isError"] is False and "receipt_version:" in ask["content"][0]["text"]
    assert str(vault) in ask["content"][0]["text"]
    assert replies[3]["result"]["isError"] is True
    assert replies[4]["error"]["code"] == -32601


def test_no_vault_is_said_plainly(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "OBSIDIAN_VAULT"}
    env["KROUTER_VAULT_FILE"] = str(tmp_path / "missing")
    replies = _talk(env, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "krouter_status", "arguments": {}}})
    res = replies[0]["result"]
    assert res["isError"] is True and "one-line install" in res["content"][0]["text"]


def test_router_scripts_find_the_recorded_vault(tmp_path):
    vault = tmp_path / "v"
    shutil.copytree(REPO / "template", vault)
    vf = tmp_path / "vault-file"
    vf.write_text(str(vault) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "OBSIDIAN_VAULT"}
    env.update({"KROUTER_VAULT_FILE": str(vf), "KROUTER_NO_QUERY_LOG": "1"})
    for argv in ([sys.executable, str(SCRIPTS / "route_knowledge.py"), "status"],
                 *([["/bin/sh", str(SCRIPTS / "route_knowledge.sh"), "status"]] if os.name != "nt" else [])):
        res = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=120)
        assert res.returncode == 0 and "route: status" in res.stdout, res.stderr
