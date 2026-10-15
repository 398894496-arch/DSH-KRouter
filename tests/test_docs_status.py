"""Every entry file an agent may read on its own carries the same, current status block (scripts/sync_status.py)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_status_block_is_in_sync_everywhere():
    res = subprocess.run([sys.executable, str(ROOT / "scripts/sync_status.py"), "--check"], capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr + " — edit docs/STATUS*.md, then run scripts/sync_status.py"
