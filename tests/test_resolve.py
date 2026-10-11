import os

from resolve import (
    distill_gate,
    is_key_name,
    models_url,
    parse_vault_page,
    usable,
    writer_field_of,
    writer_invoke,
    writer_kind,
    writer_ok,
    writer_probe_argv,
)


def test_placeholders_are_unusable():
    assert usable("") is False
    assert usable("YOUR_DEEPSEEK_API_KEY") is False
    assert usable("CHANGE_ME") is False
    assert usable("sk-your-key") is False
    assert usable("sk-live-looking") is True


def test_parse_vault_page_skips_comments_and_placeholders():
    text = """
# DEEPSEEK_API_KEY=sk-live-looking
```env
# OPENAI_API_KEY=YOUR_OPENAI_API_KEY
DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
```
"""
    assert parse_vault_page(text) == {}


def test_parse_vault_page_reads_live_line():
    text = '```env\nDEEPSEEK_API_KEY="sk-live-looking"\nOPENAI_BASE_URL=https://api.example/v1\n```\n'
    found = parse_vault_page(text)
    assert found["DEEPSEEK_API_KEY"] == "sk-live-looking"
    assert found["OPENAI_BASE_URL"] == "https://api.example/v1"


def test_unnamed_key_uses_openai_base_url():
    assert is_key_name("FOO_API_KEY")
    url = models_url("FOO_API_KEY", {"OPENAI_BASE_URL": "https://api.example/v1"})
    assert url == "https://api.example/v1/models"
    assert models_url("FOO_API_KEY", {}) is None


def test_grok_probe_argv():
    kind, argv = writer_probe_argv("/Users/x/.grok/bin/grok")
    assert kind == "grok"
    assert argv == ["/Users/x/.grok/bin/grok", "models"]


def test_grok_agent_symlink():
    kind, argv = writer_probe_argv("/Users/x/.grok/bin/agent")
    assert kind == "grok"
    assert argv[-1] == "models"


def test_path_agent_refused():
    kind, argv = writer_probe_argv("/usr/local/bin/agent")
    assert kind == "path-agent"
    assert argv is None
    assert writer_field_of("/usr/local/bin/agent", "path-agent") == "missing"


def test_codex_login_status():
    kind, argv = writer_probe_argv("/Applications/ChatGPT.app/Contents/Resources/codex")
    assert kind == "codex"
    assert argv[-2:] == ["login", "status"]


def test_claude_auth_status():
    kind, argv = writer_probe_argv("/opt/homebrew/bin/claude")
    assert kind == "claude"
    assert argv[-2:] == ["auth", "status"]


def test_writer_ok_and_kind():
    assert writer_ok("grok:ok")
    assert not writer_ok("grok:unauth")
    assert not writer_ok("path-agent")
    assert writer_kind("codex:ok") == "codex"


def test_grok_invoke_uses_vault_cwd(tmp_path):
    prompt = tmp_path / "PROMPT.md"
    prompt.write_text("seal", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    argv = writer_invoke("/Users/x/.grok/bin/grok", prompt, vault)
    assert "--model" in argv
    assert "grok-4.6" in argv
    assert "--prompt-file" in argv
    assert "--cwd" in argv
    assert str(vault) in argv
    assert "bypassPermissions" in argv
    assert "acceptEdits" not in argv
    assert "--always-approve" in argv
    assert "--sandbox" in argv


def test_timer_router_skips_live_skill(monkeypatch, tmp_path):
    live = tmp_path / "obsidian-knowledge-router" / "scripts" / "route_knowledge.sh"
    live.parent.mkdir(parents=True)
    live.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("KROUTER_ROUTER", str(live))
    from resolve import bundled_router, timer_router

    got = timer_router()
    assert got == bundled_router()
    assert "obsidian-knowledge-router" not in str(got)


def test_run_cli_writer_leaves_pending(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    writer = tmp_path / "grok"
    writer.write_text("#!/bin/sh\n", encoding="utf-8")
    writer.chmod(0o755)
    monkeypatch.setenv("TARGET_DATE", "2026-08-21")

    class Fake:
        returncode = 0

    monkeypatch.setattr("resolve.subprocess.run", lambda *a, **k: Fake())
    from resolve import bundled_router, run_cli_writer

    assert run_cli_writer(str(writer), vault, bundled_router()) == 0
    pending = vault / "05 时间日志" / "2026-08" / "21｜待总结.md"
    assert pending.is_file()
    assert "to-summarize" in pending.read_text(encoding="utf-8")


def test_codex_invoke_isolates_vault(tmp_path):
    prompt = tmp_path / "PROMPT.md"
    prompt.write_text("seal", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    argv = writer_invoke("/Applications/ChatGPT.app/Contents/Resources/codex", prompt, vault)
    assert argv[-1] == "-"
    assert "-C" in argv
    assert str(vault) in argv


def test_collect_keys_reads_install_keys_file(tmp_path, monkeypatch):
    from resolve import collect_keys

    vault = tmp_path / "vault"
    vault.mkdir()
    keys_file = tmp_path / "keys.env"
    keys_file.write_text('export DEEPSEEK_API_KEY="sk-live-looking"\n', encoding="utf-8")
    monkeypatch.setenv("KROUTER_KEYS_ENV", str(keys_file))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert collect_keys(vault)["DEEPSEEK_API_KEY"] == "sk-live-looking"


def test_pasted_page_key_moves_into_the_keys_file(tmp_path, monkeypatch):
    from resolve import collect_keys, key_page

    vault = tmp_path / "vault"
    page = key_page(vault)
    page.parent.mkdir(parents=True)
    page.write_text("```env\nDEEPSEEK_API_KEY=sk-live-page\n```\n", encoding="utf-8")
    keys_file = tmp_path / "keys.env"
    keys_file.write_text("DEEPSEEK_API_KEY=sk-live-file\n", encoding="utf-8")
    monkeypatch.setenv("KROUTER_KEYS_ENV", str(keys_file))

    assert collect_keys(vault)["DEEPSEEK_API_KEY"] == "sk-live-page"  # a newly pasted key still wins
    # …but it no longer lives in the vault: it moved into the keys file, which only the host can read
    assert "sk-live-page" not in page.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-live-page" in keys_file.read_text(encoding="utf-8")
    assert "sk-live-file" not in keys_file.read_text(encoding="utf-8")
    if os.name != "nt":  # POSIX permissions; Windows keeps the file in the user's profile
        assert oct(keys_file.stat().st_mode & 0o777) == "0o600"


def test_collect_keys_ignores_placeholders(tmp_path, monkeypatch):
    from resolve import collect_keys

    vault = tmp_path / "vault"
    vault.mkdir()
    keys_file = tmp_path / "keys.env"
    keys_file.write_text("DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY\n", encoding="utf-8")
    monkeypatch.setenv("KROUTER_KEYS_ENV", str(keys_file))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert "DEEPSEEK_API_KEY" not in collect_keys(vault)


def test_distill_gate_skips_without_key():
    ok, code, msg = distill_gate(
        {
            "key": "missing",
            "writer": "missing",
            "writer_probe": "unset",
            "key_page": "/tmp/key.md",
        }
    )
    assert ok is False
    assert code == 0
    assert "distill skipped" in msg


def test_distill_gate_cli_login_is_enough():
    ok, code, msg = distill_gate(
        {
            "key": "missing",
            "writer": "present",
            "writer_probe": "codex:ok",
            "key_page": "/tmp/key.md",
        }
    )
    assert ok is True
    assert code == 0
    assert msg == ""


def test_distill_gate_api_key_alone_is_enough():
    ok, code, msg = distill_gate(
        {
            "key": "present",
            "writer": "missing",
            "writer_probe": "unset",
            "key_page": "/tmp/key.md",
        }
    )
    assert ok is True
    assert code == 0
    assert msg == ""
