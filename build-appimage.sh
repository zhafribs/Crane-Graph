#!/usr/bin/env bash
# Build the Crane Graph AppImage.
#
# Requires a Python venv with:  PyQt5, python-appimage
#   python3 -m venv .venv
#   .venv/bin/python -m pip install PyQt5 python-appimage
#
# Run from the project root:
#   ./build-appimage.sh
set -euo pipefail

APP_NAME="crane-graph"
VERSION="V1.0.0"
FINAL_NAME="${APP_NAME}-${VERSION}.appimage"

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv/bin"
APPIMAGE_TOOL="$VENV/python-appimage"
APPDIR="$ROOT/packaging/appdir/crane-graph-app"
DIST="$ROOT/dist"

if [ ! -x "$APPIMAGE_TOOL" ]; then
    echo "ERROR: python-appimage not found in $VENV" >&2
    echo "Run: $ROOT/.venv/bin/python -m pip install python-appimage" >&2
    exit 1
fi

# python-appimage copies the mode bits of its apprun.sh template onto the
# built AppRun. If that template lost its exec bit, the AppImage will fail
# with "execv error: Permission denied" - make sure it is executable.
APPRUN_TEMPLATE="$(ls "$ROOT"/.venv/lib/*/site-packages/python_appimage/data/apprun.sh 2>/dev/null | head -1)"
if [ -n "$APPRUN_TEMPLATE" ] && [ ! -x "$APPRUN_TEMPLATE" ]; then
    echo ">> Fixing python-appimage apprun.sh template permissions ..."
    chmod +x "$APPRUN_TEMPLATE"
fi

# The icon is checked in rather than generated.
#
# It used to be drawn by `packaging/make_icon.py`, which was lost along with the rest
# of the source and could not be recovered from the AppImage -- an AppImage bundles
# what the program *runs*, and a build script is never run from inside one.  The icon
# it produced did survive, so that is now the source of truth and this no longer calls
# a generator.  See the README.
ICON="$APPDIR/crane-graph-app.png"
if [ ! -f "$ICON" ]; then
    echo "ERROR: icon missing at $ICON" >&2
    echo "It is checked into the repository; a clone without it cannot build." >&2
    exit 1
fi
echo ">> Using checked-in application icon: $ICON"

mkdir -p "$DIST"

# Make the crane_graph package importable by python-appimage (local+ bundling)
export PYTHONPATH="$ROOT"

echo ">> Building AppImage (downloads base image + PyQt5, may take a while) ..."
cd "$DIST"
"$APPIMAGE_TOOL" build app "$APPDIR"

echo ">> Normalising output name ..."
for f in ./*.AppImage; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    rm -f "$DIST/$FINAL_NAME"
    mv -f "$f" "$DIST/$FINAL_NAME"
    break
done
chmod +x "$DIST/$FINAL_NAME"
echo "DONE: $DIST/$FINAL_NAME"
