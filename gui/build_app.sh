#!/usr/bin/env bash
# Build a self-contained macOS drag-and-drop app (no Python required).
#
#   bash gui/build_app.sh
#
# Why a droplet (not a Tkinter window): this machine's only Python is 3.9.6,
# whose bundled Tk 8.5 crashes on macOS 26 ("macOS 26 required, have 16"), and
# there is no newer Python available. So the UI is a native AppleScript droplet
# that wraps a frozen, Tk-free CLI binary. Drag .clvz / .musicxml files (or a
# folder) onto the app icon; converted files appear next to the originals.
#
# Output:  gui/dist/Clover変換.app
set -euo pipefail
cd "$(dirname "$0")/.."

PYI="${PYI:-clover2xml/.venv/bin/pyinstaller}"
APP="gui/dist/Clover変換.app"

echo "==> 1/3  freeze CLI binary (no Tk)"
rm -rf gui/dist gui/build gui/clover_batch.spec gui/clover_gui.spec
# universal2 = Intel(x86_64) + Apple Silicon(arm64). Requires a universal2
# Python (the macOS Command Line Tools Python is universal2).
ARCH_FLAG="--target-arch universal2"
"$PYI" \
  --name clover-batch \
  --noconfirm --clean \
  --console \
  $ARCH_FLAG \
  --exclude-module tkinter --exclude-module _tkinter \
  --paths clover2xml \
  --collect-submodules clover2xml \
  --collect-all defusedxml \
  --distpath gui/dist --workpath gui/build --specpath gui \
  gui/clover_batch.py >/dev/null
echo "    -> gui/dist/clover-batch/ (universal2)"

echo "==> 2/3  compile AppleScript droplet"
osacompile -o "$APP" gui/droplet.applescript

echo "==> 3/3  embed the binary inside the .app"
mkdir -p "$APP/Contents/Resources/bin"
cp -R gui/dist/clover-batch "$APP/Contents/Resources/bin/"

echo "==> built: $APP"
echo "    Finder で .clvz / .musicxml をアイコンにドラッグ&ドロップ。"
