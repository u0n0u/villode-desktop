#!/usr/bin/env bash
set -euo pipefail

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./uninstall.sh [--purge]

Options:
  --purge  Also remove ~/.config/villode-desktop data.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

"$HOME/.local/bin/villode-desktop" --quit >/dev/null 2>&1 || true
rm -f "$HOME/.local/bin/villode-desktop"
rm -rf "$HOME/.local/share/villode-desktop/home"
rm -f "$HOME/.config/hypr/conf.d/villode-desktop.conf"

HYPR_MAIN="$HOME/.config/hypr/hyprland.conf"
if [ -f "$HYPR_MAIN" ]; then
  sed -i.bak '/villode-desktop\.conf/d' "$HYPR_MAIN"
fi

if [ "$PURGE" -eq 1 ]; then
  rm -rf "$HOME/.config/villode-desktop"
fi

if command -v hyprctl >/dev/null 2>&1 && hyprctl monitors >/dev/null 2>&1; then
  hyprctl reload >/dev/null || true
fi

echo "Uninstalled Villode Desktop."
