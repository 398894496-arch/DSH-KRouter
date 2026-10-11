#!/bin/sh
# One line for anyone on macOS / Linux:
#   curl -fsSL https://raw.githubusercontent.com/398894496-arch/DSH-KRouter/main/scripts/bootstrap.sh | sh
# Options pass through to bootstrap.py, e.g. `| sh -s -- --vault ~/MyVault --lang en`.
# Fetches the latest release (a tag, never main) into ~/.dsh-krouter/<tag>, checks its SHA-256 against the release's
# SHA256SUMS, points ~/.dsh-krouter/current at it, and runs scripts/bootstrap.py from there. Run again to upgrade;
# `| KROUTER_TAG=v0.11.2 sh` stays on one release. From a clone, it uses the clone.
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
  VER=${TAG#v}
  BASE="${KROUTER_RELEASE_BASE:-https://github.com/$REPO/releases/download/$TAG}"
  if curl -fsSL "$BASE/dsh-krouter-$VER.tgz" -o "$TMP/pkg.tgz" && curl -fsSL "$BASE/SHA256SUMS" -o "$TMP/SHA256SUMS"; then
    # 发布包带校验和：对不上就停，不装
    WANT=$(grep " dsh-krouter-$VER.tgz\$" "$TMP/SHA256SUMS" | cut -d' ' -f1)
    GOT=$( (sha256sum "$TMP/pkg.tgz" 2>/dev/null || shasum -a 256 "$TMP/pkg.tgz") | cut -d' ' -f1)
    if [ -z "$WANT" ] || [ "$WANT" != "$GOT" ]; then
      printf '%s\n' "校验和不符，已停止 / checksum mismatch for dsh-krouter-$VER.tgz; nothing installed."
      rm -rf "$TMP"
      exit 1
    fi
    tar -xzf "$TMP/pkg.tgz" -C "$TMP"
    rm -rf "$DEST"
    mv "$TMP/package" "$DEST"
    printf '%s\n' "sha256 verified: dsh-krouter-$VER.tgz"
  else
    printf '%s\n' "注意：$TAG 没有带校验和的发布包，改用源码归档（未校验） / note: $TAG has no checksummed package; using the source archive (unverified)."
    curl -fsSL "https://github.com/$REPO/archive/refs/tags/$TAG.tar.gz" -o "$TMP/src.tar.gz"
    tar -xzf "$TMP/src.tar.gz" -C "$TMP"
    rm -rf "$DEST"
    mv "$TMP"/DSH-KRouter-* "$DEST"
  fi
  rm -rf "$TMP"
fi
ln -sfn "$DEST" "$HOME_DIR/current"
printf '%s\n' "DSH-KRouter $TAG → $HOME_DIR/current"
exec python3 "$HOME_DIR/current/scripts/bootstrap.py" "$@"
