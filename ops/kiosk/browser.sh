#!/bin/bash
set -Eeuo pipefail
browser=""
for candidate in chromium chromium-browser google-chrome; do
  if command -v "$candidate" >/dev/null; then browser="$(command -v "$candidate")"; break; fi
done
[[ -n "$browser" ]] || { echo "Instala Chromium antes de iniciar el kiosco" >&2; exit 1; }
profile="$HOME/.local/share/quibar-browser"
if [[ -d /snap/chromium/current ]]; then profile="$HOME/snap/chromium/common/quibar-browser"; fi
mkdir -p "$profile"
exec "$browser" --kiosk --no-first-run --no-default-browser-check --incognito \
  --overscroll-history-navigation=0 --disable-session-crashed-bubble \
  --user-data-dir="$profile" http://127.0.0.1:8000/
