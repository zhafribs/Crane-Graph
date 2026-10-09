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
VERSION="V1.0.1"
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

# Pin the python-appimage base image when BASE_IMAGE is set.  This skips
# python-appimage's unauthenticated GitHub API lookup for the "latest"
# image, which is unreliable under CI rate limits.  When BASE_IMAGE is a
# URL it is downloaded here first and keeps its versioned file name, since
# python-appimage derives the bundled Python version from the image's file
# name (its parser trips over the "pythonX.Y/" segment inside a raw URL).
# Leave it empty to let python-appimage pick the newest published image.
BASE_IMAGE_ARGS=()
if [ -n "${BASE_IMAGE:-}" ]; then
    case "$BASE_IMAGE" in
        http://*|https://*)
            base_file="$(basename "$BASE_IMAGE")"
            if [ ! -f "$base_file" ]; then
                echo ">> Downloading base image: $BASE_IMAGE"
                curl -fL --retry 3 -o "$base_file" "$BASE_IMAGE"
            fi
            chmod +x "$base_file"
            BASE_IMAGE="$PWD/$base_file"
            ;;
    esac
    BASE_IMAGE_ARGS=("--base-image" "$BASE_IMAGE")
    echo ">> Using pinned base image: $BASE_IMAGE"
fi

"$APPIMAGE_TOOL" build app "${BASE_IMAGE_ARGS[@]}" "$APPDIR"

echo ">> Normalising output name ..."
for f in ./*.AppImage; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    rm -f "$DIST/$FINAL_NAME"
    mv -f "$f" "$DIST/$FINAL_NAME"
    break
done
chmod +x "$DIST/$FINAL_NAME"

# Emit a .zsync beside the AppImage so existing users can update by downloading
# only the blocks that changed (AppImageUpdate).  A .zsync is bound to one
# download URL -- it names the file it describes and embeds where that file is
# served from -- so it has to be regenerated for every release.
#
# The URL defaults to the GitHub release asset:
#
#   https://github.com/<owner>/<repo>/releases/download/<tag>/<file>
#
# <owner>/<repo> is read from the `origin` remote, <tag> is the version with a
# leading "V" lower-cased (V1.0.0 -> v1.0.0) and <file> is FINAL_NAME.  Override
# any of it with ZSYNC_URL (a full URL), RELEASE_TAG or GITHUB_REPO (owner/name).
#
# zsync is optional: if zsyncmake is missing the build still succeeds, it just
# produces no .zsync.  Install it with `apt install zsync`.
if command -v zsyncmake >/dev/null 2>&1; then
    tag="${RELEASE_TAG:-v${VERSION#V}}"

    if [ -z "${GITHUB_REPO:-}" ]; then
        GITHUB_REPO="$(git -C "$ROOT" remote get-url origin 2>/dev/null \
            | sed -E 's#(git@|https?://)github\.com[:/]##; s#\.git$##' || true)"
    fi

    if [ -z "${ZSYNC_URL:-}" ] && [ -n "$GITHUB_REPO" ]; then
        ZSYNC_URL="https://github.com/$GITHUB_REPO/releases/download/$tag/$FINAL_NAME"
    fi

    if [ -n "${ZSYNC_URL:-}" ]; then
        echo ">> Generating zsync for delta updates ..."
        echo "   URL: $ZSYNC_URL"
        zsyncmake -u "$ZSYNC_URL" -o "$DIST/$FINAL_NAME.zsync" "$DIST/$FINAL_NAME"
    else
        echo ">> Skipping zsync: set ZSYNC_URL or add a GitHub 'origin' remote to enable delta updates."
    fi
else
    echo ">> Skipping zsync: zsyncmake not found (apt install zsync)."
fi

echo "DONE:"
echo "  $DIST/$FINAL_NAME"
if [ -f "$DIST/$FINAL_NAME.zsync" ]; then
    echo "  $DIST/$FINAL_NAME.zsync"
fi
