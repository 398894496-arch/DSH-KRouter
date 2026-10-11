#!/usr/bin/env python3
"""Zone names are configurable: map the default layout onto a vault that already has its own.

The code speaks the default layout (`01 项目`, `02 经验与方法`, `03 资料与证据`, `04 已完成与复盘`,
`05 时间日志`, `90 系统文件`, `Agent第二大脑.md`). A vault with other names puts one file at its root,
`krouter-zones.psv`, one `default prefix|your prefix` per line, e.g.

    90 系统文件|System
    05 时间日志|Journal
    02 经验与方法|Methods
    Agent第二大脑.md|Home.md
    02 经验与方法/Agent/用户偏好与工作约束.md|Methods/Preferences.md

The longest matching prefix wins, on path-segment boundaries. `real()` turns a default path into the
vault's path; `canon()` turns a vault path back into the default one, so tiering and log detection
keep working on the default names. No file → identity. `KROUTER_ZONES` points at another file.
"""

from __future__ import annotations

import os
from pathlib import Path

ZONES_FILE = "krouter-zones.psv"
_CACHE: dict[str, tuple[float, list[tuple[str, str]]]] = {}


def _file(vault: Path) -> Path:
    raw = os.environ.get("KROUTER_ZONES", "").strip()
    return Path(raw) if raw else Path(vault) / ZONES_FILE


def pairs(vault: Path | None) -> list[tuple[str, str]]:
    """[(default prefix, vault prefix)], longest default first. Cached per file mtime."""
    if vault is None:
        return []
    path = _file(vault)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    key = str(path)
    if key in _CACHE and _CACHE[key][0] == mtime:
        return _CACHE[key][1]
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "|" not in line:
            continue
        default, mine = (x.strip().strip("/") for x in line.split("|", 1))
        if default and mine:
            out.append((default, mine))
    out.sort(key=lambda p: -len(p[0]))
    _CACHE[key] = (mtime, out)
    return out


def _swap(rel: str, table: list[tuple[str, str]]) -> str:
    rel = rel.replace("\\", "/")
    for src, dst in table:
        if rel == src or rel.startswith(src + "/"):
            return dst + rel[len(src):]
    return rel


def real(vault: Path | None, rel: str) -> str:
    """Default-layout path → this vault's path."""
    return _swap(rel, pairs(vault))


def canon(vault: Path | None, rel: str) -> str:
    """This vault's path → default-layout path (for tiering and log detection)."""
    table = sorted(((b, a) for a, b in pairs(vault)), key=lambda p: -len(p[0]))
    return _swap(rel, table)


def path(vault: Path, rel: str) -> Path:
    """Absolute path in this vault for a default-layout path."""
    return Path(vault) / real(vault, rel)
