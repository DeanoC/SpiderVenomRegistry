#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing json file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"{path}: invalid json: {exc}")


def ensure(cond: bool, message: str) -> None:
    if not cond:
        fail(message)


def verify_package_projection(release_json: dict[str, Any], release_facts: dict[str, Any]) -> None:
    release_packages = release_json.get("packages")
    facts_packages = release_facts.get("packages")
    ensure(isinstance(release_packages, list), "release.json missing packages array")
    ensure(isinstance(facts_packages, list), "release facts missing packages array")
    release_by_id = {pkg["package_id"]: pkg for pkg in release_packages if isinstance(pkg, dict) and "package_id" in pkg}
    facts_by_id = {pkg["package_id"]: pkg for pkg in facts_packages if isinstance(pkg, dict) and "package_id" in pkg}
    ensure(set(release_by_id) == set(facts_by_id), "package projections do not match release.json")
    for package_id, release_package in release_by_id.items():
        facts_package = facts_by_id[package_id]
        for field in ("venom_id", "kind", "release_version", "channel", "digest"):
            ensure(release_package.get(field) == facts_package.get(field), f"package projection mismatch for {package_id}: {field}")


def build_bundle_release_doc(
    *,
    bundle_id: str,
    release_version: str,
    channel: str,
    published_at: str,
    package_ids: list[str],
    packages: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    min_spiderweb_version: str,
    release_json_rel_path: str,
) -> dict[str, Any]:
    primary = artifacts[0]
    return {
        "bundle_id": bundle_id,
        "release_version": release_version,
        "channel": channel,
        "publisher": "SpiderVenoms",
        "published_at": published_at,
        "artifact_version": "1",
        "package_ids": package_ids,
        "packages": packages,
        "artifacts": [
            {
                "os": artifact["os"],
                "arch": artifact["arch"],
                "url": artifact["url"],
                "sha256": artifact["sha256"],
                "size_bytes": artifact["size_bytes"],
            }
            for artifact in artifacts
        ],
        "bundle_release_path": primary["url"],
        "bundle_release_sha256": primary["sha256"],
        "manifest": release_json_rel_path,
        "min_spiderweb_version": min_spiderweb_version,
        "notes_url": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SpiderVenomRegistry v1 documents from SpiderVenoms release facts.")
    parser.add_argument("--spidervenoms-root", default=str((REPO_ROOT.parent / "SpiderVenoms").resolve()))
    parser.add_argument("--release-facts", default=None)
    parser.add_argument("--release-json", default=None)
    parser.add_argument("--out-root", default=str(REPO_ROOT))
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--key-id", default="spidervenomregistry-dev-2026-03")
    parser.add_argument("--min-spiderweb-version", default="0.5.4")
    args = parser.parse_args()

    spidervenoms_root = pathlib.Path(args.spidervenoms_root).resolve()
    release_facts_path = pathlib.Path(
        args.release_facts or spidervenoms_root / "dist" / "spidervenoms-release-facts.json"
    ).resolve()
    release_json_path = pathlib.Path(
        args.release_json or spidervenoms_root / "assets" / "bundles" / "managed-local" / "release.json"
    ).resolve()
    out_root = pathlib.Path(args.out_root).resolve()
    v1_root = out_root / "v1"
    channels_root = v1_root / "channels"
    bundles_root = v1_root / "bundles" / "managed-local"
    channels_root.mkdir(parents=True, exist_ok=True)
    bundles_root.mkdir(parents=True, exist_ok=True)

    release_facts = load_json(release_facts_path)
    release_json = load_json(release_json_path)
    ensure(isinstance(release_facts, dict), "release facts must be an object")
    ensure(isinstance(release_json, dict), "release.json must be an object")

    bundle_id = release_facts.get("bundle_id")
    release_version = release_facts.get("release_version")
    channel = release_facts.get("channel")
    published_at = release_facts.get("published_at")
    package_ids = release_facts.get("package_ids")
    packages = release_facts.get("packages")
    artifacts = release_facts.get("artifacts")
    ensure(isinstance(bundle_id, str) and bundle_id, "release facts missing bundle_id")
    ensure(isinstance(release_version, str) and release_version, "release facts missing release_version")
    ensure(isinstance(channel, str) and channel, "release facts missing channel")
    ensure(isinstance(published_at, str) and published_at, "release facts missing published_at")
    ensure(isinstance(package_ids, list) and package_ids, "release facts missing package_ids")
    ensure(isinstance(packages, list) and packages, "release facts missing packages")
    ensure(isinstance(artifacts, list) and artifacts, "release facts missing artifacts")
    verify_package_projection(release_json, release_facts)

    for artifact in artifacts:
        ensure(isinstance(artifact, dict), "artifact entry must be an object")
        url = artifact.get("url")
        sha256 = artifact.get("sha256")
        ensure(isinstance(url, str) and url, "artifact url missing")
        ensure(isinstance(sha256, str) and len(sha256) == 64, f"artifact sha256 invalid for {url}")

    release_doc = build_bundle_release_doc(
        bundle_id=bundle_id,
        release_version=release_version,
        channel=channel,
        published_at=published_at,
        package_ids=list(package_ids),
        packages=list(packages),
        artifacts=list(artifacts),
        min_spiderweb_version=args.min_spiderweb_version,
        release_json_rel_path="share/spidervenoms/bundles/managed-local/release.json",
    )
    bundle_doc_path = bundles_root / f"{release_version}.json"
    bundle_doc_path.write_text(json.dumps(release_doc, indent=2) + "\n", encoding="utf-8")

    stable_doc = {
        "channel": "stable",
        "generated_at": published_at,
        "bundles": [
            {
                "bundle_id": bundle_id,
                "head_release_version": release_version,
                "release_versions": [release_version],
                "path": f"v1/bundles/{bundle_id}/{release_version}.json",
            }
        ],
    }
    beta_doc = {
        "channel": "beta",
        "generated_at": published_at,
        "bundles": [],
    }
    dev_doc = {
        "channel": "dev",
        "generated_at": published_at,
        "bundles": [],
    }

    (channels_root / "stable.json").write_text(json.dumps(stable_doc, indent=2) + "\n", encoding="utf-8")
    (channels_root / "beta.json").write_text(json.dumps(beta_doc, indent=2) + "\n", encoding="utf-8")
    (channels_root / "dev.json").write_text(json.dumps(dev_doc, indent=2) + "\n", encoding="utf-8")

    index_doc = {
        "schema_version": "spidervenom-registry-v1",
        "publisher": "SpiderVenomRegistry",
        "generated_at": published_at,
        "keys": [
            {
                "key_id": "spidervenomregistry-dev-2026-03",
                "path": "keys/trusted-registry-keys.json",
            }
        ],
        "channels": [
            {"id": "stable", "path": "v1/channels/stable.json"},
            {"id": "beta", "path": "v1/channels/beta.json"},
            {"id": "dev", "path": "v1/channels/dev.json"},
        ],
        "bundles": [
            {
                "bundle_id": bundle_id,
                "package_ids": package_ids,
                "latest_by_channel": {
                    "stable": {
                        "release_version": release_version,
                        "path": f"v1/bundles/{bundle_id}/{release_version}.json",
                    }
                },
            }
        ],
    }
    index_doc_path = v1_root / "index.json"
    index_doc_path.write_text(json.dumps(index_doc, indent=2) + "\n", encoding="utf-8")

    signer = REPO_ROOT / "scripts" / "registry_envelope.py"
    subprocess.run(
        [
            "python3",
            str(signer),
            "sign",
            "--keys",
            str(REPO_ROOT / "keys" / "trusted-registry-keys.json"),
            "--key-id",
            args.key_id,
            "--private-key",
            str(pathlib.Path(args.private_key).resolve()),
            str(index_doc_path),
            str(channels_root / "stable.json"),
            str(channels_root / "beta.json"),
            str(channels_root / "dev.json"),
            str(bundle_doc_path),
        ],
        check=True,
    )
    print(f"registry generated at: {v1_root}")


if __name__ == "__main__":
    main()
