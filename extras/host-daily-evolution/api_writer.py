#!/usr/bin/env python3
"""Bundled distill writer: an API key is enough. No grok / Codex / claude required.

Reads OBSIDIAN_VAULT, calls a mainstream chat API with PROMPT.md, writes markdown
only inside the vault. Never prints secrets. Never edits canonical_sources.psv
or the key page.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

TIMEOUT = 180
MAX_ROUNDS = 12
MAX_FILE_BYTES = 120_000
DENIED_NAMES = frozenset({"canonical_sources.psv", "自进化钥匙.md"})

# (env name, chat url, flagship default, style)
CHAT_SPECS: list[tuple[str, str, str, str]] = [
    ("DEEPSEEK_API_KEY", "https://api.deepseek.com/chat/completions", "deepseek-reasoner", "openai"),
    ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions", "gpt-4.1", "openai"),
    ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/messages", "claude-opus-4-20250514", "anthropic"),
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
    ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
    ("GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
    ("GOOGLE_GENERATIVE_AI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent", "gemini-2.5-pro", "gemini"),
]

FLAGSHIP_NEEDLES = (
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

HERE = Path(__file__).resolve().parent
PROMPT = HERE / "PROMPT.md"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a markdown file relative to the vault root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a markdown file relative to the vault root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_md",
            "description": "List markdown files under a vault-relative directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route",
            "description": "Run route_knowledge.sh. route is status|search|correction|preference|memory|project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["route"],
            },
        },
    },
]


def vault_root() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not raw:
        raise SystemExit("OBSIDIAN_VAULT is not set")
    return Path(raw).resolve()


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


def model_override(keys: dict[str, str], extra: dict[str, str]) -> str:
    for name in ("MODEL", "DISTILL_MODEL", "KROUTER_DISTILL_MODEL"):
        val = (keys.get(name) or extra.get(name) or os.environ.get(name, "")).strip()
        if val:
            return val
    return ""


def pick_chat(keys: dict[str, str], extra: dict[str, str] | None = None) -> dict[str, str] | None:
    """Choose a chat endpoint. Return metadata only — never the secret."""
    extra = extra or {}
    override = model_override(keys, extra)
    base = (extra.get("OPENAI_BASE_URL") or extra.get("OPENAI_API_BASE") or "").rstrip("/")
    for name, url, model, style in CHAT_SPECS:
        if name not in keys:
            continue
        chosen = dict(name=name, url=url, model=override or model, style=style, locked="override" if override else "default")
        if name == "OPENAI_API_KEY" and base:
            chosen["url"] = base + "/chat/completions"
        return chosen
    for name, val in keys.items():
        if name in {"OPENAI_BASE_URL", "OPENAI_API_BASE", "MODEL", "DISTILL_MODEL", "KROUTER_DISTILL_MODEL"} or not val:
            continue
        if not (name.endswith("_API_KEY") or name.endswith("_API_TOKEN")):
            continue
        if not base:
            return None
        return {
            "name": name,
            "url": base + "/chat/completions",
            "model": override or "gpt-4.1",
            "style": "openai",
            "locked": "override" if override else "default",
        }
    return None


def safe_vault_path(vault: Path, rel: str) -> Path | None:
    rel = (rel or "").strip().lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    name = Path(rel).name
    if name in DENIED_NAMES:
        return None
    if rel.endswith("canonical_sources.psv"):
        return None
    if "Clippings/" in rel.replace("\\", "/"):
        return None
    path = (vault / rel).resolve()
    try:
        path.relative_to(vault)
    except ValueError:
        return None
    if path.suffix.lower() != ".md":
        return None
    return path


def parse_files_payload(text: str) -> list[dict[str, str]]:
    raw = (text or "").strip()
    if not raw:
        return []
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json|markdown|md)?\n", "", raw)
        raw = re.sub(r"\n```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    files = data.get("files") if isinstance(data, dict) else data
    if not isinstance(files, list):
        return []
    out: list[dict[str, str]] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        content = item.get("content")
        if path and isinstance(content, str):
            out.append({"path": path, "content": content})
    return out


def apply_files(vault: Path, files: list[dict[str, str]]) -> int:
    written = 0
    for item in files[:8]:
        path = safe_vault_path(vault, item["path"])
        if path is None:
            continue
        body = item["content"]
        if len(body.encode("utf-8")) > MAX_FILE_BYTES:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not body.endswith("\n"):
            body += "\n"
        path.write_text(body, encoding="utf-8")
        written += 1
    return written


def target_day() -> date:
    raw = os.environ.get("TARGET_DATE", "").strip()
    if raw:
        return date.fromisoformat(raw)
    return date.today() - timedelta(days=1)


def collect_snapshot(vault: Path, day: date) -> str:
    logs = vault / "05 时间日志"
    names: list[str] = []
    if logs.is_dir():
        for p in sorted(logs.rglob("*.md")):
            try:
                rel = str(p.relative_to(vault))
            except ValueError:
                continue
            names.append(rel)
            if len(names) >= 40:
                break
    health = vault / "90 系统文件" / "自动化" / "日更健康.md"
    health_text = ""
    if health.is_file():
        health_text = health.read_text(encoding="utf-8", errors="replace")[:2000]
    return json.dumps(
        {
            "target_date": day.isoformat(),
            "logs": names,
            "health": health_text,
        },
        ensure_ascii=False,
    )


def router_script() -> Path | None:
    from resolve import timer_router

    path = timer_router()
    return path if path.is_file() else None


def run_route(route: str, query: str = "") -> str:
    script = router_script()
    if script is None:
        return "router missing"
    argv = [str(script), route]
    if query:
        argv.append(query)
    env = os.environ.copy()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return "router failed"
    text = (proc.stdout or "") + (proc.stderr or "")
    return text[:8000]


def tool_impl(vault: Path, name: str, args: dict) -> str:
    if name == "read_file":
        path = safe_vault_path(vault, str(args.get("path") or ""))
        if path is None or not path.is_file():
            return "denied or missing"
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
    if name == "write_file":
        files = [{"path": str(args.get("path") or ""), "content": str(args.get("content") or "")}]
        n = apply_files(vault, files)
        return "wrote" if n else "denied"
    if name == "list_md":
        rel = str(args.get("path") or ".").strip() or "."
        root = (vault / rel).resolve()
        try:
            root.relative_to(vault)
        except ValueError:
            return "denied"
        if not root.is_dir():
            return "missing"
        names = []
        for p in sorted(root.rglob("*.md")):
            try:
                names.append(str(p.relative_to(vault)))
            except ValueError:
                continue
            if len(names) >= 60:
                break
        return "\n".join(names) or "(empty)"
    if name == "route":
        return run_route(str(args.get("route") or "status"), str(args.get("query") or ""))
    return "unknown tool"


def _http_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"DSH-KRouter: chat API HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit("DSH-KRouter: chat API network failed") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("DSH-KRouter: chat API returned non-JSON") from exc


def openai_headers(key: str, name: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if name == "OPENROUTER_API_KEY":
        headers["HTTP-Referer"] = "https://github.com/398894496-arch/DSH-KRouter"
        headers["X-Title"] = "DSH-KRouter"
    return headers


def write_pending(vault: Path, day: date, reason: str) -> None:
    month = vault / "05 时间日志" / day.strftime("%Y-%m")
    path = month / f"{day.strftime('%d')}｜待总结.md"
    if path.exists():
        return
    month.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: {day.strftime('%d')}｜待总结\ntype: daily-log\nstatus: to-summarize\ndate: {day.isoformat()}\n---\n\n"
        f"# {day.strftime('%d')}｜待总结\n\n{reason}\n",
        encoding="utf-8",
    )


def run_openai_tools(vault: Path, spec: dict[str, str], key: str, user: str) -> int:
    messages = [
        {"role": "system", "content": PROMPT.read_text(encoding="utf-8") if PROMPT.is_file() else ""},
        {"role": "user", "content": user},
    ]
    wrote = 0
    for _ in range(MAX_ROUNDS):
        data = _http_json(
            spec["url"],
            {
                "model": spec["model"],
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
            },
            openai_headers(key, spec["name"]),
        )
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if tool_calls:
            messages.append(msg)
            for call in tool_calls:
                fn = (call.get("function") or {})
                name = fn.get("name") or ""
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = tool_impl(vault, name, args if isinstance(args, dict) else {})
                if name == "write_file" and result == "wrote":
                    wrote += 1
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or name,
                        "content": result,
                    }
                )
            continue
        files = parse_files_payload(content)
        wrote += apply_files(vault, files)
        break
    return wrote


def run_single_shot(vault: Path, spec: dict[str, str], key: str, user: str) -> int:
    prompt_text = (PROMPT.read_text(encoding="utf-8") if PROMPT.is_file() else "") + "\n\n" + user
    prompt_text += (
        "\n\nWhen finished, output JSON only: "
        '{"files":[{"path":"05 时间日志/YYYY-MM/DD｜summary.md","content":"..."}]}'
    )
    if spec["style"] == "anthropic":
        data = _http_json(
            spec["url"],
            {
                "model": spec["model"],
                "max_tokens": 8192,
                "messages": [{"role": "user", "content": prompt_text}],
            },
            {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        blocks = data.get("content") or []
        text = "".join(b.get("text") or "" for b in blocks if isinstance(b, dict))
    elif spec["style"] == "gemini":
        url = spec["url"]
        if "key=" not in url:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"key": key})
        data = _http_json(
            url,
            {"contents": [{"parts": [{"text": prompt_text}]}]},
            {"Content-Type": "application/json"},
        )
        cands = data.get("candidates") or []
        parts = (((cands[0] if cands else {}).get("content") or {}).get("parts") or [])
        text = "".join(p.get("text") or "" for p in parts if isinstance(p, dict))
    else:
        data = _http_json(
            spec["url"],
            {"model": spec["model"], "messages": [{"role": "user", "content": prompt_text}]},
            openai_headers(key, spec["name"]),
        )
        text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    return apply_files(vault, parse_files_payload(text))


def _http_get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def catalog_ids(spec: dict[str, str], key: str) -> list[str]:
    style = spec.get("style")
    if style == "anthropic":
        data = _http_get_json(
            "https://api.anthropic.com/v1/models",
            {"x-api-key": key, "anthropic-version": "2023-06-01", "Accept": "application/json"},
        )
        rows = data.get("data") or []
        return [str(r.get("id") or "") for r in rows if isinstance(r, dict)]
    if style == "gemini":
        q = urllib.parse.urlencode({"key": key})
        data = _http_get_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?{q}",
            {"Accept": "application/json"},
        )
        rows = data.get("models") or []
        ids = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name") or "")
            ids.append(name.split("/")[-1] if name else "")
        return ids
    url = spec["url"].replace("/chat/completions", "/models")
    data = _http_get_json(url, openai_headers(key, spec["name"]))
    rows = data.get("data") or []
    return [str(r.get("id") or "") for r in rows if isinstance(r, dict)]


def apply_flagship_lock(spec: dict[str, str], key: str) -> dict[str, str]:
    if spec.get("locked") == "override":
        return spec
    ids = catalog_ids(spec, key)
    if ids:
        spec["model"] = lock_flagship(ids, spec.get("model") or "")
        spec["locked"] = "catalog"
    if spec.get("style") == "gemini":
        spec["url"] = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + spec["model"]
            + ":generateContent"
        )
    return spec


def run(keys: dict[str, str], extra: dict[str, str] | None = None) -> int:
    vault = vault_root()
    extra = extra or {}
    spec = pick_chat(keys, extra)
    if spec is None:
        print("DSH-KRouter: no chat endpoint for the vault-page key.", file=sys.stderr)
        return 1
    secret = keys.get(spec["name"], "")
    spec = apply_flagship_lock(spec, secret)
    day = target_day()
    user = (
        f"Vault root: {vault}\n"
        f"Target day: {day.isoformat()} (yesterday unless TARGET_DATE is set).\n"
        f"Observed at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Locked model: {spec['model']}\n"
        f"Snapshot:\n{collect_snapshot(vault, day)}\n"
        "Use tools if available. Seal yesterday, distill, and when the five gates pass "
        "write provisional the same day. Do not write active. Do not edit the key page."
    )
    os.chdir(str(vault))
    try:
        if spec["style"] == "openai":
            try:
                wrote = run_openai_tools(vault, spec, secret, user)
            except SystemExit as exc:
                if "HTTP 4" in str(exc):
                    wrote = run_single_shot(vault, spec, secret, user)
                else:
                    raise
        else:
            wrote = run_single_shot(vault, spec, secret, user)
    except SystemExit:
        write_pending(vault, day, "chat API failed; left to-summarize.")
        raise
    if wrote == 0:
        write_pending(vault, day, "API writer produced no files; left to-summarize.")
        print("DSH-KRouter: API writer left a to-summarize note.", file=sys.stderr)
        return 0
    print(f"DSH-KRouter: API writer wrote {wrote} file(s) via {spec['name']}/{spec['model']}.")
    return 0
