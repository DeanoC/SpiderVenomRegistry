#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SPIDERVENOMS_ROOT="${SPIDERVENOMS_ROOT:-$REPO_ROOT/../SpiderVenoms}"
RELEASE_JSON_PATH="${RELEASE_JSON_PATH:-}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: missing required command: $1" >&2
    exit 1
  }
}

require_command python3

[[ -f "$REPO_ROOT/v1/index.json" ]] || {
  echo "error: missing registry index: $REPO_ROOT/v1/index.json" >&2
  exit 1
}

python3 "$REPO_ROOT/scripts/registry_envelope.py" verify \
  "$REPO_ROOT/v1/index.json" \
  "$REPO_ROOT/v1/channels/stable.json" \
  "$REPO_ROOT/v1/channels/beta.json" \
  "$REPO_ROOT/v1/channels/dev.json" \
  "$REPO_ROOT/v1/bundles/managed-local/"*.json

python3 - "$REPO_ROOT" "$SPIDERVENOMS_ROOT" <<'PY'
import json
import pathlib
import sys

repo_root = pathlib.Path(sys.argv[1])
venoms_root = pathlib.Path(sys.argv[2])

index = json.loads((repo_root / "v1/index.json").read_text())
stable = json.loads((repo_root / "v1/channels/stable.json").read_text())
bundle_paths = sorted((repo_root / "v1/bundles/managed-local").glob("*.json"))
assert bundle_paths, "missing managed-local bundle registry docs"
bundle = json.loads(bundle_paths[-1].read_text())

release_json_override = pathlib.Path(__import__("os").environ["RELEASE_JSON_PATH"]) if __import__("os").environ.get("RELEASE_JSON_PATH") else None
release_json_path = release_json_override or (venoms_root / "assets/bundles/managed-local/release.json")
release = json.loads(release_json_path.read_text())

assert index["schema_version"] == "spidervenom-registry-v1"
assert stable["channel"] == "stable"
assert bundle["bundle_id"] == release["bundle_id"]
assert bundle["release_version"] == release["release_version"]
assert bundle["package_ids"] == [pkg["package_id"] for pkg in release["packages"]]
PY

echo "registry check ok"
