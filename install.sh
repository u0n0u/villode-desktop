#!/usr/bin/env bash
set -euo pipefail

WITH_DEPS=0
SETUP_HYPRLAND=1
START_DESKTOP=1

for arg in "$@"; do
  case "$arg" in
    --with-deps) WITH_DEPS=1 ;;
    --no-hyprland) SETUP_HYPRLAND=0 ;;
    --no-start) START_DESKTOP=0 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./install.sh [--with-deps] [--no-hyprland] [--no-start]

Options:
  --with-deps    Install GTK3, WebKitGTK and media dependencies.
  --no-hyprland  Do not write Hyprland integration files.
  --no-start     Do not start the desktop layer after installation.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_BIN="$SCRIPT_DIR/bin/villode-desktop"
SOURCE_HOME="$SCRIPT_DIR/home"
INSTALL_BIN="$HOME/.local/bin/villode-desktop"
INSTALL_HOME="$HOME/.local/share/villode-desktop/home"
HYPR_DIR="$HOME/.config/hypr"
HYPR_MAIN="$HYPR_DIR/hyprland.conf"
HYPR_INCLUDE_DIR="$HYPR_DIR/conf.d"
HYPR_INCLUDE="$HYPR_INCLUDE_DIR/villode-desktop.conf"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

check_deps() {
  python3 - <<'PY' >/dev/null 2>&1
import cairo
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, GtkLayerShell, WebKit2
PY
}

install_deps() {
  if need_cmd pacman; then
    sudo pacman -S --needed python python-gobject python-cairo gtk3 \
      gtk-layer-shell webkit2gtk-4.1 gstreamer gst-libav gst-plugins-bad \
      gst-plugins-ugly gst-plugin-va
  elif need_cmd apt; then
    sudo apt update
    sudo apt install -y python3 python3-gi python3-cairo \
      gir1.2-gtk-3.0 gir1.2-gtk-layer-shell-0.1 gir1.2-webkit2-4.1 \
      gstreamer1.0-libav gstreamer1.0-plugins-good \
      gstreamer1.0-plugins-bad
  elif need_cmd dnf; then
    sudo dnf install -y python3 python3-gobject python3-cairo gtk3 \
      gtk-layer-shell webkit2gtk4.1 gstreamer1-plugins-good \
      gstreamer1-plugins-bad-free gstreamer1-libav
  else
    echo "No supported package manager found. Install GTK3, GtkLayerShell, WebKitGTK 4.1 and GStreamer manually." >&2
    return 1
  fi
}

write_hyprland_config() {
  mkdir -p "$HYPR_INCLUDE_DIR"
  cat > "$HYPR_INCLUDE" <<'EOF'
# Villode Desktop
$desktop = villode-desktop

exec-once = villode-desktop --daemon
bind = $mod SHIFT, D, exec, $desktop --toggle
EOF

  mkdir -p "$HYPR_DIR"
  touch "$HYPR_MAIN"
  sed -i \
    -e '/^[[:space:]]*\$desktop[[:space:]]*=[[:space:]]*villode-desktop[[:space:]]*$/d' \
    -e '/^[[:space:]]*exec-once[[:space:]]*=[[:space:]]*villode-desktop --daemon[[:space:]]*$/d' \
    -e '/^[[:space:]]*bind[[:space:]]*=[[:space:]]*\$mod SHIFT, D, exec, \$desktop --toggle[[:space:]]*$/d' \
    "$HYPR_MAIN"
  if ! grep -Eq 'source *=.*villode-desktop\.conf' "$HYPR_MAIN"; then
    {
      echo
      echo "# Villode Desktop"
      echo "source = ~/.config/hypr/conf.d/villode-desktop.conf"
    } >> "$HYPR_MAIN"
  fi
}

if [ ! -x "$SOURCE_BIN" ]; then
  echo "Missing executable: $SOURCE_BIN" >&2
  exit 1
fi
if [ ! -f "$SOURCE_HOME/index.html" ]; then
  echo "Missing default home: $SOURCE_HOME/index.html" >&2
  exit 1
fi

if ! check_deps; then
  if [ "$WITH_DEPS" -eq 1 ]; then
    install_deps
  else
    echo "Missing Villode Desktop dependencies." >&2
    echo "Run again with: ./install.sh --with-deps" >&2
    exit 1
  fi
fi

mkdir -p "$(dirname "$INSTALL_BIN")" "$INSTALL_HOME/assets"
install -m 755 "$SOURCE_BIN" "$INSTALL_BIN"
install -m 644 "$SOURCE_HOME/index.html" "$INSTALL_HOME/index.html"
install -m 644 "$SOURCE_HOME/assets/villode-glass-bg.png" \
  "$INSTALL_HOME/assets/villode-glass-bg.png"
python3 -m py_compile "$INSTALL_BIN"

if [ "$SETUP_HYPRLAND" -eq 1 ]; then
  write_hyprland_config
  if need_cmd hyprctl && hyprctl monitors >/dev/null 2>&1; then
    hyprctl reload >/dev/null || true
  fi
fi

if [ "$START_DESKTOP" -eq 1 ]; then
  "$INSTALL_BIN" --reload
fi

echo "Installed: $INSTALL_BIN"
echo "Default home: $INSTALL_HOME/index.html"
if [ "$SETUP_HYPRLAND" -eq 1 ]; then
  echo "Hyprland config: $HYPR_INCLUDE"
fi
if [ "$START_DESKTOP" -eq 1 ]; then
  echo "Desktop layer started."
fi
