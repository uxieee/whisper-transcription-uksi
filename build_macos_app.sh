#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"
APP_NAME="Whisper Canvas"
ICON_SOURCE="$SCRIPT_DIR/assets/app_icon_source.png"
ICON_ICNS="$SCRIPT_DIR/assets/app_icon.icns"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Error: virtual environment not found at $VENV_PYTHON"
  echo "Create the venv first, then install dependencies."
  exit 1
fi

"$VENV_PIP" install --upgrade pip >/dev/null
"$VENV_PIP" install pyinstaller >/dev/null
"$VENV_PIP" install -r "$SCRIPT_DIR/requirements-gui.txt" >/dev/null

if [[ -f "$ICON_SOURCE" ]]; then
  ICONSET_DIR="$SCRIPT_DIR/assets/app.iconset"
  rm -rf "$ICONSET_DIR"
  mkdir -p "$ICONSET_DIR"

  sips -z 16 16 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  sips -z 64 64 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$ICON_SOURCE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null

  iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"
fi

PYINSTALLER_ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --add-data "$SCRIPT_DIR/config.json:."
  --collect-all whisper
  --collect-all pyannote.audio
  --collect-all pyannote.core
  --collect-all torch
  --hidden-import whisper
  --hidden-import pyannote.audio
  --hidden-import pyannote.core
  "$SCRIPT_DIR/gui.py"
)

if [[ -f "$ICON_ICNS" ]]; then
  PYINSTALLER_ARGS=(--icon "$ICON_ICNS" "${PYINSTALLER_ARGS[@]}")
fi

"$VENV_PYTHON" -m PyInstaller "${PYINSTALLER_ARGS[@]}"

echo
echo "Build complete: $SCRIPT_DIR/dist/$APP_NAME.app"
echo "Open it by double-clicking in Finder."
