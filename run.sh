#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BIN="$SCRIPT_DIR/bin/villode-desktop"
SOURCE_HOME="$SCRIPT_DIR/home"
INSTALL_HOME="$HOME/.local/share/villode-desktop/home"

python3 -m py_compile "$BIN"
mkdir -p "$INSTALL_HOME/assets"
install -m 644 "$SOURCE_HOME/index.html" "$INSTALL_HOME/index.html"
install -m 644 "$SOURCE_HOME/assets/villode-glass-bg.png" \
  "$INSTALL_HOME/assets/villode-glass-bg.png"
install -m 644 "$SOURCE_HOME/assets/villode-midnight-glass.png" \
  "$INSTALL_HOME/assets/villode-midnight-glass.png"
"$BIN" --reload
