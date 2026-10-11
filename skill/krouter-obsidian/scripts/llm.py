#!/usr/bin/env python3
"""One model channel for the nightly scripts: API key first, then an already-logged-in CLI.

Same order as the daily writer (PROTOCOL rule 7). Keys come from the process environment, then
`KROUTER_KEYS_ENV` (default `~/.dsh-krouter-keys.env`), then the vault page
`90 系统文件/自动化/自进化钥匙.md`. Values are never printed. The model is `KROUTER_LEARN_MODEL`,
else `KROUTER_DISTILL_MODEL`, else a provider default; a provider with no known model is skipped
rather than guessed. With no usable key, `claude` / `codex` on PATH. A host that sets
`KROUTER_LEARN_CLI` (or passes `--cli`) has picked a CLI on purpose; it goes first.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

KEY_LINE = re.compile(r"^(?:export\s+)?([A-Z][A-Z0-9_]+)=(.*)$")
PLACEHOLDERS = ("YOUR_", "CHANGE_ME", "REPLACE", "TODO", "sk-your", "PASTE_")
TIMEOUT = 900
# provider key → (chat endpoint base, default model or "" when the host must choose)
OPENAI_COMPATIBLE = {
    "OPENAI_API_KEY": ("https://api.openai.com/v1", ""),
    "DEEPSEEK_API_KEY": ("https://api.deepseek.com", "deepseek-chat"),
    "OPENROUTER_API_KEY": ("https://openrouter.ai/api/v1", ""),
    "XAI_API_KEY": ("https://api.x.ai/v1", ""),
    "MOONSHOT_API_KEY": ("https://api.moonshot.ai/v1", ""),
    "DASHSCOPE_API_KEY": ("https://dashscope.aliyuncs.com/compatible-mode/v1", ""),
    "SILICONFLOW_API_KEY": ("https://api.siliconflow.cn/v1", ""),
}
ANTHROPIC_DEFAULT = "claude-opus-5-5"


class NoModel(RuntimeError):
    """No key and no logged-in CLI: the caller skips its step."""


def _usable(val: str) -> bool:
    val = (val or "").strip().strip('"').strip("'")
    return bool(val) and not any(val.upper().startswith(p.upper()) for p in PLACEHOLDERS)


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        m = KEY_LINE.match(raw.strip())
        if m and _usable(m.group(2)):
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def collect_keys(vault: Path | None) -> dict[str, str]:
    keys = {k: v for k, v in os.environ.items() if k.endswith(("_API_KEY", "_BASE_URL", "_MODEL")) and _usable(v)}
    env_file = Path(os.environ.get("KROUTER_KEYS_ENV") or Path.home() / ".dsh-krouter-keys.env")
    if env_file.is_file():
        keys.update(_parse(env_file.read_text(encoding="utf-8", errors="replace")))
    if vault is not None:
        page = vault / "90 系统文件" / "自动化" / "自进化钥匙.md"
        if page.is_file():
            keys.update(_parse(page.read_text(encoding="utf-8", errors="replace")))
    return keys


def _model(keys: dict[str, str], default: str) -> str:
    return keys.get("KROUTER_LEARN_MODEL") or os.environ.get("KROUTER_LEARN_MODEL") \
        or keys.get("KROUTER_DISTILL_MODEL") or os.environ.get("KROUTER_DISTILL_MODEL") or default


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={**headers, "Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if "127.0.0.1" in url else urllib.request.build_opener()
    with opener.open(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def plan(vault: Path | None = None) -> list[tuple[str, str]]:
    """Ordered (kind, detail) the channel would try. No secrets in the output."""
    keys = collect_keys(vault)
    steps: list[tuple[str, str]] = []
    explicit = os.environ.get("KROUTER_LEARN_CLI", "")
    if explicit and Path(explicit).is_file() and os.access(explicit, os.X_OK):
        # the host named a CLI on purpose (e.g. a subscription model): honor it before any key
        steps.append(("cli", explicit))
    if "ANTHROPIC_API_KEY" in keys:
        steps.append(("anthropic-api", _model(keys, ANTHROPIC_DEFAULT)))
    for name, (base, default) in OPENAI_COMPATIBLE.items():
        if name in keys:
            model = _model(keys, default)
            if model:
                steps.append((f"openai-compatible:{name}", model))
    cli = shutil.which("claude") or shutil.which("codex") or ""
    if not explicit and cli and Path(cli).is_file() and os.access(cli, os.X_OK):
        steps.append(("cli", cli))
    return steps


def complete(prompt: str, vault: Path | None = None) -> str:
    """Return the model's text, trying each available channel once in order."""
    keys = collect_keys(vault)
    errors: list[str] = []
    for kind, detail in plan(vault):
        try:
            if kind == "anthropic-api":
                data = _post("https://api.anthropic.com/v1/messages",
                             {"x-api-key": keys["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                             {"model": detail, "max_tokens": 8000, "messages": [{"role": "user", "content": prompt}]})
                return "".join(b.get("text", "") for b in data.get("content", []))
            if kind.startswith("openai-compatible:"):
                name = kind.split(":", 1)[1]
                base = keys.get(name.replace("_API_KEY", "_BASE_URL")) or (keys.get("OPENAI_BASE_URL") if name == "OPENAI_API_KEY" else "") \
                    or OPENAI_COMPATIBLE[name][0]
                data = _post(base.rstrip("/") + "/chat/completions", {"Authorization": f"Bearer {keys[name]}"},
                             {"model": detail, "messages": [{"role": "user", "content": prompt}]})
                return data["choices"][0]["message"]["content"]
            if kind == "cli":
                name = Path(detail).name.lower()
                if name.startswith("codex"):
                    argv = [detail, "exec", "--skip-git-repo-check", "-"]
                    proc = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=TIMEOUT)
                else:
                    argv = [detail, "--print", "--tools", "", "--output-format", "text", "--no-session-persistence"]
                    model = os.environ.get("KROUTER_LEARN_MODEL", "")
                    if model:
                        argv += ["--model", model]
                    proc = subprocess.run(argv + [prompt], capture_output=True, text=True, timeout=TIMEOUT)
                if proc.returncode != 0:
                    raise RuntimeError((proc.stderr or proc.stdout)[-200:])
                return proc.stdout
        except (urllib.error.URLError, OSError, KeyError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{kind}: {str(exc)[:160]}")
    if errors:
        raise RuntimeError("all model channels failed: " + " | ".join(errors))
    raise NoModel("no API key with a known model and no logged-in CLI; set *_API_KEY (+ KROUTER_LEARN_MODEL) or log in claude / codex")
