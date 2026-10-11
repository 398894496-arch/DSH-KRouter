#!/usr/bin/env python3
"""One-step install for anyone: a vault, the router, the daily timer. No terminal knowledge assumed.

Usually started by `bootstrap.sh` (macOS / Linux) or `bootstrap.ps1` (Windows), which find Python and fetch the
latest release; can also be run from a clone. What it does, in order:

1. Pick the language (`--lang zh|en`, default: the system's) and the matching template.
2. Pick the vault: `--vault PATH`, else `OBSIDIAN_VAULT`, else a new folder `Documents/第二大脑` (`Second Brain`).
   A new or empty folder gets the template. An existing vault keeps every file; only missing skeleton files are
   added (`--vault` on a vault of your own). Nothing is ever overwritten.
3. Install the router skill, the agent rules and the daily timer (launchd / systemd / cron / Windows task), keeping
   an existing alias table. Re-running it is an upgrade.
4. Check for a model: a logged-in CLI or an API key. If there is none, say in one sentence what to do.
5. Open the new vault in Obsidian when Obsidian is installed.

`--dry-run` prints the plan and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import platform
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
MSG = {
    "zh": {
        "plan": "计划", "vault_new": "新建知识库", "vault_merge": "使用已有知识库（只补缺失的骨架文件，不覆盖任何文件）",
        "vault_ours": "已是第二大脑知识库（升级）", "added": "补上的文件", "skill": "路由器", "timer": "每日定时任务",
        "model_ok": "模型通道", "model_none": "还没有可用的模型：登录一个 AI 编程工具（Claude Code 运行 `claude`、Codex、grok 等任选其一），"
        "或把 API key 写进 {keys}（一行，如 DEEPSEEK_API_KEY=sk-…）。之后每晚自动整理，不用再做任何事。",
        "done": "装好了。知识库在：{vault}\n每天 09:10 自动封账、整理、学习；出问题会弹通知。agent 查询走：{router}",
        "obsidian": "已在 Obsidian 里打开这个知识库。", "obsidian_none": "装上 Obsidian（https://obsidian.md）后，选「打开本地仓库」→ {vault}",
        "py_old": "需要 Python 3.9 或更新版本，当前是 {v}。",
    },
    "en": {
        "plan": "Plan", "vault_new": "New vault", "vault_merge": "Existing vault (adds only missing skeleton files; overwrites nothing)",
        "vault_ours": "Already a Second Brain vault (upgrade)", "added": "files added", "skill": "Router", "timer": "Daily timer",
        "model_ok": "Model lane", "model_none": "No model yet: log in to one AI coding CLI (`claude`, Codex, grok, …), "
        "or put an API key in {keys} (one line, e.g. DEEPSEEK_API_KEY=sk-…). After that it runs every night on its own.",
        "done": "Done. Your vault: {vault}\nEvery day at 09:10 it seals, distills and learns; problems show up as notifications. Agents query: {router}",
        "obsidian": "Opened the vault in Obsidian.", "obsidian_none": "Install Obsidian (https://obsidian.md), then “Open folder as vault” → {vault}",
        "py_old": "Python 3.9 or newer is required; this is {v}.",
    },
}
KEEP = ("canonical_sources.psv", "canonical_alias_ledger.jsonl")


def system_lang() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        if os.environ.get(var, "").lower().startswith("zh"):
            return "zh"
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=5).stdout
            first = next((ln.strip(' ",()') for ln in out.splitlines() if ln.strip(' ",()')), "")
            return "zh" if first.lower().startswith("zh") else "en"
        except (OSError, subprocess.TimeoutExpired):
            pass
    if WINDOWS:
        try:
            import ctypes

            return "zh" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x04 else "en"
        except (AttributeError, OSError):
            pass
    loc = (locale.getlocale()[0] or "").lower()
    return "zh" if loc.startswith(("zh", "chinese")) else "en"


def template_for(lang: str) -> Path:
    zh = ROOT / "template-zh"
    return zh if lang == "zh" and zh.is_dir() else ROOT / "template"


def default_vault(lang: str) -> Path:
    return Path.home() / "Documents" / ("第二大脑" if lang == "zh" else "Second Brain")


def vault_state(vault: Path) -> str:
    if not vault.exists() or (vault.is_dir() and not any(p for p in vault.iterdir() if p.name != ".DS_Store")):
        return "new"
    if (vault / "Agent第二大脑.md").is_file() or (vault / "krouter-zones.psv").is_file() \
            or (vault / "90 系统文件" / "自动化" / "日更健康.md").is_file():
        return "ours"
    return "merge"


def lay_down(template: Path, vault: Path, dry: bool) -> list[str]:
    """Copy template files that are missing in the vault. Never overwrites."""
    added = []
    for src in sorted(template.rglob("*")):
        if not src.is_file() or src.name == ".DS_Store":
            continue
        rel = src.relative_to(template)
        dst = vault / rel
        if dst.exists():
            continue
        added.append(rel.as_posix())
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return added


def install_posix(vault: Path, dry: bool) -> int:
    skill = Path(os.environ.get("KROUTER_SKILL_HOME") or Path.home() / ".agents/skills/krouter-obsidian")
    argv = ["/bin/sh", str(ROOT / "scripts/install.sh")] + (["--upgrade"] if skill.exists() else [])
    if dry:
        print("  " + " ".join(argv))
        return 0
    return subprocess.run(argv, env={**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_BOOTSTRAP": "1"}).returncode


def install_windows(vault: Path, dry: bool, timer: bool) -> int:
    """install.sh, for Windows: skill (keeping the alias table), agent rules, alias table into the vault, timer."""
    home = Path.home()
    skill = Path(os.environ.get("KROUTER_SKILL_HOME") or home / ".agents/skills/krouter-obsidian")
    rules = Path(os.environ.get("KROUTER_CURSOR_RULE") or home / ".cursor/rules/krouter-obsidian.mdc")
    ask = Path(os.environ.get("KROUTER_ASK_RULE") or home / ".cursor/rules/ask-product.mdc")
    if dry:
        print(f"  copy skill → {skill}\n  rules → {rules.parent}\n  timer: {'scheduled task' if timer else 'skipped'}")
        return 0
    kept = {}
    for name in KEEP:
        p = skill / "scripts" / name
        if p.is_file():
            kept[name] = p.read_bytes()
    if skill.exists():
        shutil.rmtree(skill)
    shutil.copytree(ROOT / "skill/krouter-obsidian", skill)
    for name, data in kept.items():
        (skill / "scripts" / name).write_bytes(data)
    rules.parent.mkdir(parents=True, exist_ok=True)
    ask.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "extras/cursor/krouter-obsidian.mdc", rules)
    shutil.copy2(ROOT / "extras/cursor/ask-product.mdc", ask)
    table = vault / "90 系统文件" / "canonical_sources.psv"
    if not table.exists() and (vault / "90 系统文件").is_dir():
        old = kept.get("canonical_sources.psv")
        sample = (ROOT / "skill/krouter-obsidian/scripts/canonical_sources.psv").read_bytes()
        table.write_bytes(old if old and old != sample else sample)
    env = {**os.environ, "OBSIDIAN_VAULT": str(vault)}
    subprocess.run([sys.executable, str(ROOT / "extras/host-daily-evolution/resolve.py"), "--sync-health", "--offline"],
                   env=env, capture_output=True)
    if timer:
        ps = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/install_windows_task.ps1"),
              "-Vault", str(vault), "-Python", sys.executable]
        res = subprocess.run(ps, env=env, capture_output=True, text=True)
        print((res.stdout or res.stderr).strip())
        return res.returncode
    return 0


def model_lane(vault: Path) -> str:
    """The lane the writer would really use: keys are probed, CLIs must be logged in (resolve.py --status)."""
    res = subprocess.run([sys.executable, str(ROOT / "extras/host-daily-evolution/resolve.py"), "--status"],
                         env={**os.environ, "OBSIDIAN_VAULT": str(vault)}, capture_output=True, text=True, timeout=180)
    try:
        st = json.loads(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ""
    if st.get("lane") == "cli-login":
        return f"{Path(st.get('writer_path') or '').name or st.get('kind')} (CLI)"
    if st.get("lane") == "api-key":
        return "API key"
    return ""


def open_in_obsidian(vault: Path) -> bool:
    url = "obsidian://open?path=" + urllib.parse.quote(str(vault))
    try:
        if platform.system() == "Darwin":
            if not (Path("/Applications/Obsidian.app").exists() or (Path.home() / "Applications/Obsidian.app").exists()):
                return False
            return subprocess.run(["open", url], capture_output=True).returncode == 0
        if WINDOWS:
            if not (Path(os.environ.get("APPDATA", "")) / "obsidian").exists():
                return False
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        if shutil.which("xdg-open") and (Path.home() / ".config/obsidian").exists():
            return subprocess.run(["xdg-open", url], capture_output=True).returncode == 0
    except OSError:
        return False
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="One-step install: vault + router + daily timer")
    ap.add_argument("--vault", default="")
    ap.add_argument("--lang", choices=["zh", "en", "auto"], default="auto")
    ap.add_argument("--no-timer", action="store_true", help="skip the daily timer (Windows: no scheduled task)")
    ap.add_argument("--no-open", action="store_true", help="do not open the vault in Obsidian")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    lang = system_lang() if args.lang == "auto" else args.lang
    t = MSG[lang]
    if sys.version_info < (3, 9):
        print(t["py_old"].format(v=platform.python_version()))
        return 1
    vault = Path(args.vault or os.environ.get("OBSIDIAN_VAULT") or default_vault(lang)).expanduser().resolve()
    state = vault_state(vault)
    template = template_for(lang)
    print(f"{t['plan']}: {t['vault_' + state]} → {vault}")
    added = lay_down(template, vault, args.dry_run)
    if added and state != "new":
        print(f"  {t['added']}: {len(added)}" + "".join(f"\n    {a}" for a in added[:12]) + ("\n    …" if len(added) > 12 else ""))
    if args.no_timer:
        os.environ["KROUTER_SKIP_LAUNCHD"] = os.environ["KROUTER_SKIP_TIMER"] = "1"
    rc = install_windows(vault, args.dry_run, not args.no_timer) if WINDOWS else install_posix(vault, args.dry_run)
    if rc != 0:
        return rc
    if args.dry_run:
        return 0
    lane = model_lane(vault)
    keys = os.environ.get("KROUTER_KEYS_ENV") or str(Path.home() / ".dsh-krouter-keys.env")
    print(f"{t['model_ok']}: {lane}" if lane else t["model_none"].format(keys=keys))
    skill = Path(os.environ.get("KROUTER_SKILL_HOME") or Path.home() / ".agents/skills/krouter-obsidian")
    router = skill / "scripts" / ("route_knowledge.py" if WINDOWS else "route_knowledge.sh")
    print(t["done"].format(vault=vault, router=router))
    if state == "new" and not args.no_open:
        print(t["obsidian"] if open_in_obsidian(vault) else t["obsidian_none"].format(vault=vault))
    print(json.dumps({"vault": str(vault), "lang": lang, "state": state, "added": len(added), "model": lane or None},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
