"""Where the vault is, for a caller that was not told: `OBSIDIAN_VAULT`, else the path the installer recorded.

The one-line install writes the vault path to `~/.config/krouter/vault` (one line; `KROUTER_VAULT_FILE` points
elsewhere), so an agent, the MCP server or a plugin can route without anyone exporting a variable first.
"""

from __future__ import annotations

import os
from pathlib import Path


def vault_file() -> Path:
    raw = os.environ.get("KROUTER_VAULT_FILE", "")
    if raw:
        return Path(raw).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "krouter" / "vault"


def vault_path() -> str:
    raw = os.environ.get("OBSIDIAN_VAULT", "")
    if raw:
        return raw
    try:
        line = vault_file().read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except (OSError, IndexError):
        return ""
    return str(Path(line).expanduser()) if line else ""


def remember(vault: Path) -> Path:
    path = vault_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(vault) + "\n", encoding="utf-8")
    return path
