#!/bin/sh
# One line for anyone on macOS / Linux:
#   curl -fsSL https://raw.githubusercontent.com/398894496-arch/DSH-KRouter/main/scripts/bootstrap.sh | sh
# Options pass through to bootstrap.py, e.g. `| sh -s -- --vault ~/MyVault --lang en`.
# Fetches the latest release (a pinned tag, not main) into ~/.dsh-krouter/<tag>, points ~/.dsh-krouter/current at
# it, and runs scripts/bootstrap.py from there. Run again to upgrade. From a clone, it uses the clone.
set -eu

REPO="398894496-arch/DSH-KRouter"
HOME_DIR="${KROUTER_HOME:-$HOME/.dsh-krouter}"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "需要 Python 3 / Python 3 is required."
  case "$(uname -s)" in
    Darwin) printf '%s\n' "macOS: 终端运行 xcode-select --install，或从 https://www.python.org 下载安装，然后重跑这一行。" ;;
    *) printf '%s\n' "Linux: sudo apt install python3（或你的发行版对应命令），然后重跑这一行。" ;;
  esac
  exit 1
fi

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || true)
if [ -n "$HERE" ] && [ -f "$HERE/bootstrap.py" ] && [ -d "$HERE/../skill/krouter-obsidian" ]; then
  exec python3 "$HERE/bootstrap.py" "$@"
fi

TAG=${KROUTER_TAG:-$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')}
DEST="$HOME_DIR/$TAG"
if [ ! -f "$DEST/scripts/bootstrap.py" ]; then
  mkdir -p "$HOME_DIR"
  TMP=$(mktemp -d "${TMPDIR:-/tmp}/krouter-dl.XXXXXX")
  curl -fsSL "https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz" -o "$TMP/src.tar.gz"
  tar -xzf "$TMP/src.tar.gz" -C "$TMP"
  rm -rf "$DEST"
  mv "$TMP"/DSH-KRouter-* "$DEST"
  rm -rf "$TMP"
fi
ln -sfn "$DEST" "$HOME_DIR/current"
printf '%s\n' "DSH-KRouter $TAG → $HOME_DIR/current"
exec python3 "$HOME_DIR/current/scripts/bootstrap.py" "$@"
