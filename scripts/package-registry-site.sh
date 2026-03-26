#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$REPO_ROOT/dist"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    *)
      echo "usage: $0 [--out-dir <dir>]" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$OUT_DIR"
SITE_DIR="$OUT_DIR/site"
rm -rf "$SITE_DIR"
mkdir -p "$SITE_DIR/keys"

cp -R "$REPO_ROOT/v1" "$SITE_DIR/v1"
cp "$REPO_ROOT/keys/trusted-registry-keys.json" "$SITE_DIR/keys/trusted-registry-keys.json"
touch "$SITE_DIR/.nojekyll"

ARCHIVE_PATH="$OUT_DIR/spidervenom-registry-v1.tar.gz"
rm -f "$ARCHIVE_PATH" "$ARCHIVE_PATH.sha256"
tar -C "$SITE_DIR" -czf "$ARCHIVE_PATH" .

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$ARCHIVE_PATH" | awk '{print $1}' > "$ARCHIVE_PATH.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$ARCHIVE_PATH" | awk '{print $1}' > "$ARCHIVE_PATH.sha256"
else
  echo "error: missing shasum or sha256sum" >&2
  exit 1
fi

echo "registry site packaged:"
echo "  site: $SITE_DIR"
echo "  archive: $ARCHIVE_PATH"
