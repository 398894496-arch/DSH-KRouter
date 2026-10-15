# Optional Cursor hook

Default `install.sh` does not enable this.

**An accident guard, not a security boundary.** It matches paths by string and knows Cursor's tool names only, so a
relative path or a `cd` first gets past it. It stops a slip, not an agent set on doing it.

1. Copy `exec-gate.py` somewhere writable.
2. Put an absolute `python3 /that/path/exec-gate.py` command into `~/.cursor/hooks.json` (see `hooks.json.example`).
3. The hook process must see `OBSIDIAN_VAULT`.

Denied: mutating `$OBSIDIAN_VAULT/Clippings`, quitting or reloading Obsidian. This is not a general sandbox.
