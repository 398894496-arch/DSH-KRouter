#!/usr/bin/env python3
"""One model channel for the nightly scripts and the daily writer: API key first, then a logged-in CLI.

This file owns the provider table and the flagship lock; `extras/host-daily-evolution/api_writer.py`
imports them from here, so the nightly steps and the writer see the same providers in the same order
(PROTOCOL rule 7). Keys come from the process environment, then `KROUTER_KEYS_ENV` (default
`~/.dsh-krouter-keys.env`), then the vault page `90 系统文件/自动化/自进化钥匙.md`. Values are never
printed and never put in a URL. The model is `KROUTER_LEARN_MODEL`, else `KROUTER_DISTILL_MODEL`, else
the provider's flagship from its live catalog, else the table's default. With no usable key,
`claude` / `codex` on PATH. A host that sets `KROUTER_LEARN_CLI` (or passes `--cli`) has picked a CLI
on purpose; it goes first.
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
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"

# (env name, chat url, flagship default, style). Order is the order both lanes try keys in.
CHAT_SPECS: list[tuple[str, str, str, str]] = [
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/chat/completions", "deepseek-reasoner", "openai"),
    ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions", "gpt-4.1", "openai"),
    ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages", "claude-opus-5-5", "anthropic"),
    ("XAI_API_KEY", "https://api.x.ai/v1/chat/completions", "grok-4", "openai"),
    ("GROQ_API_KEY", "https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b", "openai"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions", "anthropic/claude-sonnet-4", "openai"),
    ("MOONSHOT_API_KEY", "https://api.moonshot.ai/v1/chat/completions", "kimi-k2-0711-preview", "openai"),
    ("KIMI_API_KEY", "https://api.moonshot.ai/v1/chat/completions", "kimi-k2-0711-preview", "openai"),
    ("DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-max", "openai"),
    ("ZHIPUAI_API_KEY", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-plus", "openai"),
    ("GLM_API_KEY", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-plus", "openai"),
    ("SILICONFLOW_API_KEY", "https://api.siliconflow.cn/v1/chat/completions", "deepseek-ai/DeepSeek-R1", "openai"),
    ("TOGETHER_API_KEY", "https://api.together.xyz/v1/chat/completions", "deepseek-ai/DeepSeek-R1", "openai"),
    ("FIREWORKS_API_KEY", "https://api.fireworks.ai/inference/v1/chat/completions", "accounts/fireworks/models/deepseek-r1", "openai"),
    ("MISTRAL_API_KEY", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest", "openai"),
    ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1/chat/completions", "gpt-oss-120b", "openai"),
    ("NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1/chat/completions", "deepseek-ai/deepseek-r1", "openai"),
    ("PERPLEXITY_API_KEY", "https://api.perplexity.ai/chat/completions", "sonar-pro", "openai"),
    ("GEMINI_API_KEY", f"{GEMINI}/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
    ("GOOGLE_API_KEY", f"{GEMINI}/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
    ("GOOGLE_GENERATIVE_AI_API_KEY", f"{GEMINI}/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
]

# First needle that matches scores the id; newer generations sit above older ones.
FLAGSHIP_NEEDLES = (
    ("opus-5", 102),
    ("opus-4", 100),
    ("claude-opus", 98),
    ("grok-4.6", 96),
    ("grok-4", 92),
    ("gpt-5", 90),
    ("o3", 86),
    ("deepseek-reasoner", 85),
    ("deepseek-r1", 84),
    ("claude-sonnet-4", 82),
    ("gpt-4.1", 80),
    ("gemini-2.5-pro", 78),
    ("qwen-max", 76),
    ("kimi-k2", 74),
    ("glm-4.5", 72),
    ("glm-4-plus", 70),
    ("mistral-large", 68),
    ("deepseek-chat", 60),
    ("sonar-pro", 58),
)
FLAGSHIP_PENALTY = ("mini", "nano", "haiku", "lite", "small", "instant", "flash-lite", "tiny")


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


def lock_flagship(model_ids: list[str], fallback: str = "") -> str:
    """Pick the flagship id from a provider catalog. Never prefers mini/haiku/flash-lite."""
    best_id = fallback
    best_score = -10_000
    for raw in model_ids:
        mid = (raw or "").strip()
        if not mid:
            continue
        lower = mid.lower()
        score = 1
        for needle, pts in FLAGSHIP_NEEDLES:
            if needle in lower:
                score = max(score, pts)
                break
        if any(p in lower for p in FLAGSHIP_PENALTY):
            score -= 40
        if "flash" in lower and "pro" not in lower:
            score -= 20
        if score > best_score:
            best_score = score
            best_id = mid
    return best_id or fallback


def openai_headers(key: str, name: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    if name == "OPENROUTER_API_KEY":
        headers["HTTP-Referer"] = "https://github.com/398894496-arch/DSH-KRouter"
        headers["X-Title"] = "DSH-KRouter"
    return headers


def _opener(url: str):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})) if "127.0.0.1" in url else urllib.request.build_opener()


def _get_json(url: str, headers: dict[str, str]) -> dict:
    try:
        with _opener(url).open(urllib.request.Request(url, headers=headers, method="GET"), timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {}


def catalog_ids(spec: dict[str, str], key: str) -> list[str]:
    """Model ids the provider lists for this key; [] when the catalog is unreachable."""
    style = spec.get("style")
    if style == "anthropic":
        data = _get_json("https://api.anthropic.com/v1/models",
                         {"x-api-key": key, "anthropic-version": "2023-06-01", "Accept": "application/json"})
        return [str(r.get("id") or "") for r in data.get("data") or [] if isinstance(r, dict)]
    if style == "gemini":
        data = _get_json(GEMINI, {"x-goog-api-key": key, "Accept": "application/json"})
        return [str(r.get("name") or "").split("/")[-1] for r in data.get("models") or [] if isinstance(r, dict)]
    data = _get_json(spec["url"].replace("/chat/completions", "/models"), openai_headers(key, spec["name"]))
    return [str(r.get("id") or "") for r in data.get("data") or [] if isinstance(r, dict)]


def _override(keys: dict[str, str]) -> str:
    return keys.get("KROUTER_LEARN_MODEL") or os.environ.get("KROUTER_LEARN_MODEL") \
        or keys.get("KROUTER_DISTILL_MODEL") or os.environ.get("KROUTER_DISTILL_MODEL") or ""


def _post(url: str, headers: dict[str, str], body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={**headers, "Content-Type": "application/json"}, method="POST")
    with _opener(url).open(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_specs(keys: dict[str, str]) -> list[dict[str, str]]:
    """The providers this key set can reach, in table order. Metadata only — never the secret."""
    out = []
    for name, url, default, style in CHAT_SPECS:
        if name not in keys:
            continue
        base = keys.get(name.replace("_API_KEY", "_BASE_URL"), "").rstrip("/")
        if name == "OPENAI_API_KEY":
            base = base or keys.get("OPENAI_API_BASE", "").rstrip("/")
        out.append({"name": name, "url": base + "/chat/completions" if base and style == "openai" else url,
                    "model": default, "style": style})
    return out


def plan(vault: Path | None = None) -> list[tuple[str, str]]:
    """Ordered (kind, detail) the channel would try. No secrets in the output."""
    keys = collect_keys(vault)
    steps: list[tuple[str, str]] = []
    explicit = os.environ.get("KROUTER_LEARN_CLI", "")
    if explicit and Path(explicit).is_file() and os.access(explicit, os.X_OK):
        # the host named a CLI on purpose (e.g. a subscription model): honor it before any key
        steps.append(("cli", explicit))
    override = _override(keys)
    for spec in api_specs(keys):
        # without an override the model is the catalog's flagship, decided at call time
        steps.append((f"api:{spec['name']}", override or f"flagship (default {spec['model']})"))
    cli = shutil.which("claude") or shutil.which("codex") or ""
    if not explicit and cli and Path(cli).is_file() and os.access(cli, os.X_OK):
        steps.append(("cli", cli))
    return steps


def _call_api(spec: dict[str, str], key: str, model: str, prompt: str) -> str:
    if spec["style"] == "anthropic":
        data = _post(spec["url"], {"x-api-key": key, "anthropic-version": "2023-06-01"},
                     {"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": prompt}]})
        return "".join(b.get("text", "") for b in data.get("content", []) if isinstance(b, dict))
    if spec["style"] == "gemini":
        data = _post(f"{GEMINI}/{model}:generateContent", {"x-goog-api-key": key},
                     {"contents": [{"parts": [{"text": prompt}]}]})
        cands = data.get("candidates") or []
        parts = ((cands[0] if cands else {}).get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    data = _post(spec["url"], openai_headers(key, spec["name"]),
                 {"model": model, "messages": [{"role": "user", "content": prompt}]})
    return data["choices"][0]["message"]["content"]


_LOCKED: dict[str, str] = {}  # provider → flagship id, once per process


def complete(prompt: str, vault: Path | None = None) -> str:
    """Return the model's text, trying each available channel once in order."""
    keys = collect_keys(vault)
    specs = {f"api:{s['name']}": s for s in api_specs(keys)}
    override = _override(keys)
    errors: list[str] = []
    for kind, detail in plan(vault):
        try:
            if kind in specs:
                spec = specs[kind]
                key = keys[spec["name"]]
                model = override
                if not model:
                    if spec["name"] not in _LOCKED:
                        _LOCKED[spec["name"]] = lock_flagship(catalog_ids(spec, key), spec["model"])
                    model = _LOCKED[spec["name"]]
                return _call_api(spec, key, model, prompt)
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
        except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError, RuntimeError,
                subprocess.TimeoutExpired) as exc:
            errors.append(f"{kind}: {str(exc)[:160]}")
    if errors:
        raise RuntimeError("all model channels failed: " + " | ".join(errors))
    raise NoModel("no API key and no logged-in CLI; set a *_API_KEY or log in claude / codex")
