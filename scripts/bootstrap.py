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
        "或把 API key 写进 {keys}（一行，如 DEEPSEEK_API_KEY=sk-…）。夜间任务开着的话，之后每晚自动整理，不用再做任何事。",
        "done": "装好了。知识库在：{vault}\nagent 查询走：{router}",
        "obsidian": "已在 Obsidian 里打开这个知识库。", "obsidian_none": "装上 Obsidian（https://obsidian.md）后，选「打开本地仓库」→ {vault}",
        "py_old": "需要 Python 3.9 或更新版本，当前是 {v}。",
        "ask": "要开启每晚自动整理吗？开启后每天 09:10：{lane}整理昨天的记录{perm}；并把 {pages} 页规则页和主题页（约 {tokens} token）发给它，预先算好常见问题的答案。之后随时可以用 uninstall.sh 关掉。开启？[y/N] ",
        "lane_cli": "用 {cli} ", "lane_key": "用你的 API key ", "lane_none": "（等你登录一个 AI 编程工具或贴好 key 之后）",
        "perm_grok": "（在内核沙箱里运行：只能读写这个知识库、运行路由器，读不到你账户里的其他文件，包括 key 文件）",
        "perm_claude": "（只允许读写这个知识库、运行路由器，不能执行别的命令，也不能上网抓网页；但没有内核沙箱）",
        "perm_codex": "（在 Codex 沙箱里运行：只能写这个知识库，但读得到你账户里的文件，包括 key 文件）",
        "perm_key": "（直接调用 API，不在本机运行任何 agent）",
        "perm_other": "（不受限制：它以你的身份运行，能读写你账户里的任何文件）",
        "prefer_key": "更稳妥的是用 API key：它直接调用接口，不在本机运行任何 agent（把 key 贴到知识库的「自进化钥匙」页就行）。\n",
        "timer_off": "没有开启每晚自动整理。想开的时候运行：{cmd}",
        "timer_skip_noninteractive": "不是在交互终端里运行，所以没有开启每晚自动整理（需要你明确同意）。想开的时候运行：{cmd}",
    },
    "en": {
        "plan": "Plan", "vault_new": "New vault", "vault_merge": "Existing vault (adds only missing skeleton files; overwrites nothing)",
        "vault_ours": "Already a Second Brain vault (upgrade)", "added": "files added", "skill": "Router", "timer": "Daily timer",
        "model_ok": "Model lane", "model_none": "No model yet: log in to one AI coding CLI (`claude`, Codex, grok, …), "
        "or put an API key in {keys} (one line, e.g. DEEPSEEK_API_KEY=sk-…). With the nightly job on, it then runs every night on its own.",
        "done": "Done. Your vault: {vault}\nAgents query: {router}",
        "obsidian": "Opened the vault in Obsidian.", "obsidian_none": "Install Obsidian (https://obsidian.md), then “Open folder as vault” → {vault}",
        "py_old": "Python 3.9 or newer is required; this is {v}.",
        "ask": "Turn on the nightly upkeep? Every day at 09:10 it will {lane}distill yesterday{perm}, and send {pages} rule and topic pages (about {tokens} tokens) to it to precompute answers. uninstall.sh turns it off any time. Turn on? [y/N] ",
        "lane_cli": "use {cli} to ", "lane_key": "use your API key to ", "lane_none": "(once you log in to an AI coding CLI or paste a key) ",
        "perm_grok": " (in a kernel sandbox: it can read and write only this vault and run the router; nothing else in your account, keys file included)",
        "perm_claude": " (allowed only to read and write this vault and run the router: no other command, no web fetch; but no kernel sandbox)",
        "perm_codex": " (in Codex's sandbox: it writes only this vault but can read files in your account, keys file included)",
        "perm_key": " (a direct API call; no agent runs on this machine)",
        "perm_other": " (unconfined: it runs as you and can read and write any file in your account)",
        "prefer_key": "The safer choice is an API key: a direct API call, no agent runs on this machine (paste it on the vault's key page).\n",
        "timer_off": "Nightly upkeep is off. To turn it on later: {cmd}",
        "timer_skip_noninteractive": "Not run from an interactive terminal, so the nightly upkeep was not turned on (it needs your yes). To turn it on: {cmd}",
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


def ask_tty(prompt: str) -> str | None:
    """Ask on the terminal even when stdin is the piped install script (`curl … | sh`). None: no terminal."""
    if os.environ.get("KROUTER_NO_PROMPT") == "1":
        return None
    if WINDOWS:
        if not sys.stdin or not sys.stdin.isatty():
            return None
        try:
            return input(prompt)
        except EOFError:
            return None
    try:
        with open("/dev/tty", "r+", encoding="utf-8") as tty:
            tty.write(prompt)
            tty.flush()
            return tty.readline()
    except OSError:
        return None


def nightly_preview(vault: Path) -> tuple[str, str, int, int]:
    """(lane kind, CLI name, pages that would be sent, est tokens) — from resolve --status and nightly --dry-run."""
    env = {**os.environ, "OBSIDIAN_VAULT": str(vault), "KROUTER_NO_QUERY_LOG": "1"}
    kind, cli = "", ""
    res = subprocess.run([sys.executable, str(ROOT / "extras/host-daily-evolution/resolve.py"), "--status"], env=env,
                         capture_output=True, text=True, timeout=180)
    try:
        st = json.loads(res.stdout.strip().splitlines()[-1])
        if st.get("lane") == "cli-login":
            kind, cli = st.get("kind") or "other", Path(st.get("writer_path") or "").name
        elif st.get("lane") == "api-key":
            kind = "key"
    except (ValueError, IndexError):
        pass
    pages = tokens = 0
    dry = subprocess.run([sys.executable, str(ROOT / "skill/krouter-obsidian/scripts/nightly.py"), "--vault", str(vault),
                          "--dry-run"], env=env, capture_output=True, text=True, timeout=600)
    try:
        tokens = int(json.loads(dry.stdout).get("est_tokens_total") or 0)
    except ValueError:
        pass
    cards = subprocess.run([sys.executable, str(ROOT / "skill/krouter-obsidian/scripts/answer_cards.py"), "--vault", str(vault),
                            "--dry-run"], env=env, capture_output=True, text=True, timeout=600)
    try:
        pages = len(json.loads(cards.stdout.strip().splitlines()[-1]).get("would_send_pages") or [])
    except (ValueError, IndexError):
        pass
    return kind, cli, pages, tokens


def decide_timer(args: argparse.Namespace, vault: Path, t: dict) -> tuple[bool, bool]:
    """(install it, the host was asked). The nightly job runs a model with wide permissions and sends vault text:
    it is installed only on an explicit yes — `--timer`, or `y` at the prompt. No terminal to ask on: not installed."""
    if args.timer:
        return True, True
    if args.no_timer:
        return False, True
    kind, cli, pages, tokens = nightly_preview(vault)
    lane = t["lane_cli"].format(cli=cli) if kind not in ("", "key") else (t["lane_key"] if kind == "key" else t["lane_none"])
    perm = t.get(f"perm_{kind}", t["perm_other"]) if kind else ""
    prompt = (t["prefer_key"] if kind not in ("", "key") else "") + t["ask"].format(lane=lane, perm=perm, pages=pages, tokens=tokens)
    answer = ask_tty(prompt)
    if answer is None:
        return False, False
    return answer.strip().lower() in {"y", "yes", "是", "好", "开"}, True


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
    ap.add_argument("--timer", action="store_true", help="install the nightly job without asking (you have read what it does)")
    ap.add_argument("--no-timer", action="store_true", help="do not install the nightly job, and do not ask")
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
    os.environ["KROUTER_NO_TIMER"] = "1"  # 先只装只读部分：库、路由、规则；夜间任务等宿主点头再装
    rc = install_windows(vault, args.dry_run, False) if WINDOWS else install_posix(vault, args.dry_run)
    if rc != 0:
        return rc
    if args.dry_run:
        print("  nightly job: " + ("yes (--timer)" if args.timer else "no (--no-timer)" if args.no_timer else "asks first"))
        return 0
    os.environ.pop("KROUTER_NO_TIMER", None)
    timer, asked = decide_timer(args, vault, t)
    if timer:
        rc = install_windows(vault, False, True) if WINDOWS else install_posix(vault, False)
        if rc != 0:
            return rc
    else:
        cmd = f"{'python' if WINDOWS else 'python3'} \"{ROOT / 'scripts' / 'bootstrap.py'}\" --timer --vault \"{vault}\""
        print((t["timer_off"] if asked else t["timer_skip_noninteractive"]).format(cmd=cmd))
    lane = model_lane(vault)
    keys = os.environ.get("KROUTER_KEYS_ENV") or str(Path.home() / ".dsh-krouter-keys.env")
    print(f"{t['model_ok']}: {lane}" if lane else t["model_none"].format(keys=keys))
    skill = Path(os.environ.get("KROUTER_SKILL_HOME") or Path.home() / ".agents/skills/krouter-obsidian")
    router = skill / "scripts" / ("route_knowledge.py" if WINDOWS else "route_knowledge.sh")
    print(t["done"].format(vault=vault, router=router))
    if state == "new" and not args.no_open:
        print(t["obsidian"] if open_in_obsidian(vault) else t["obsidian_none"].format(vault=vault))
    print(json.dumps({"vault": str(vault), "lang": lang, "state": state, "added": len(added), "model": lane or None,
                      "timer": timer},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
