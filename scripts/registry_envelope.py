#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_KEYS_PATH = REPO_ROOT / "keys" / "trusted-registry-keys.json"
SIGNATURE_SCHEME = "ed25519-sha256-v1"
REGISTRY_DOCUMENT_PURPOSE = "venom_registry_document"


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def canonicalize(value: Any, *, strip_envelope_fields: bool) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key in sorted(value):
            if strip_envelope_fields and key in {"digest", "signature"}:
                continue
            out[key] = canonicalize(value[key], strip_envelope_fields=False)
        return out
    if isinstance(value, list):
        return [canonicalize(item, strip_envelope_fields=False) for item in value]
    return value


def canonical_payload_bytes(value: dict[str, Any]) -> bytes:
    payload = canonicalize(value, strip_envelope_fields=True)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing json file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"{path}: invalid json: {exc}")


def load_trusted_keys(keys_path: pathlib.Path) -> dict[str, dict[str, Any]]:
    raw = load_json(keys_path)
    if not isinstance(raw, dict) or not raw:
        fail(f"trusted key store is empty: {keys_path}")
    return raw


def require_trusted_key_policy(
    trusted_keys: dict[str, dict[str, Any]],
    key_id: str,
    *,
    allow_signing: bool,
    label: str,
) -> dict[str, Any]:
    trusted_key = trusted_keys.get(key_id)
    if trusted_key is None:
        fail(f"{label}: untrusted key id: {key_id}")
    if trusted_key.get("publisher") != "SpiderVenomRegistry":
        fail(f"{label}: key {key_id} publisher mismatch")
    if trusted_key.get("scheme") != SIGNATURE_SCHEME:
        fail(f"{label}: trusted key store scheme mismatch for {key_id}")
    purposes = trusted_key.get("document_purposes")
    if not isinstance(purposes, list) or REGISTRY_DOCUMENT_PURPOSE not in purposes:
        fail(f"{label}: key {key_id} is not trusted for {REGISTRY_DOCUMENT_PURPOSE}")
    status = trusted_key.get("status")
    if status == "revoked":
        fail(f"{label}: key {key_id} is revoked")
    if status != "active":
        fail(f"{label}: key {key_id} has unsupported status {status!r}")
    usage = trusted_key.get("usage")
    if allow_signing and usage != "sign_and_verify":
        fail(f"{label}: key {key_id} is not allowed to sign")
    if usage not in {"sign_and_verify", "verify_only"}:
        fail(f"{label}: key {key_id} has unsupported usage {usage!r}")
    return trusted_key


def sign_digest(private_key_path: pathlib.Path, digest_hex: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_path = pathlib.Path(tmpdir) / "digest.bin"
        signature_path = pathlib.Path(tmpdir) / "signature.bin"
        digest_path.write_bytes(bytes.fromhex(digest_hex))
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key_path),
                "-rawin",
                "-in",
                str(digest_path),
                "-out",
                str(signature_path),
            ],
            check=True,
            capture_output=True,
        )
        return base64.b64encode(signature_path.read_bytes()).decode("ascii")


def verify_digest_signature(public_key_hex: str, digest_hex: str, signature_b64: str) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_path = pathlib.Path(tmpdir) / "digest.bin"
        signature_path = pathlib.Path(tmpdir) / "signature.bin"
        public_key_der = pathlib.Path(tmpdir) / "public.der"
        public_key_pem = pathlib.Path(tmpdir) / "public.pem"
        digest_path.write_bytes(bytes.fromhex(digest_hex))
        signature_path.write_bytes(base64.b64decode(signature_b64, validate=True))
        public_key_der.write_bytes(bytes.fromhex("302a300506032b6570032100" + public_key_hex))
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-pubin",
                "-inform",
                "DER",
                "-in",
                str(public_key_der),
                "-out",
                str(public_key_pem),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_key_pem),
                "-rawin",
                "-in",
                str(digest_path),
                "-sigfile",
                str(signature_path),
            ],
            check=True,
            capture_output=True,
        )


def sign_object(
    value: dict[str, Any],
    *,
    key_id: str,
    private_key_path: pathlib.Path,
    trusted_keys: dict[str, dict[str, Any]],
    label: str,
) -> None:
    require_trusted_key_policy(trusted_keys, key_id, allow_signing=True, label=label)
    digest_hex = hashlib.sha256(canonical_payload_bytes(value)).hexdigest()
    value["digest"] = f"sha256:{digest_hex}"
    value["signature"] = {
        "scheme": SIGNATURE_SCHEME,
        "key_id": key_id,
        "value": sign_digest(private_key_path, digest_hex),
    }


def verify_object(value: dict[str, Any], trusted_keys: dict[str, dict[str, Any]], label: str) -> None:
    digest = value.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        fail(f"{label}: missing sha256 digest")
    signature = value.get("signature")
    if not isinstance(signature, dict):
        fail(f"{label}: missing signature object")
    scheme = signature.get("scheme")
    key_id = signature.get("key_id")
    signature_value = signature.get("value")
    if scheme != SIGNATURE_SCHEME:
        fail(f"{label}: unsupported signature scheme: {scheme!r}")
    if not isinstance(key_id, str) or not key_id:
        fail(f"{label}: missing signature key_id")
    if not isinstance(signature_value, str) or not signature_value:
        fail(f"{label}: missing signature value")
    trusted_key = require_trusted_key_policy(trusted_keys, key_id, allow_signing=False, label=label)
    expected_digest = hashlib.sha256(canonical_payload_bytes(value)).hexdigest()
    if digest != f"sha256:{expected_digest}":
        fail(f"{label}: digest mismatch")
    verify_digest_signature(trusted_key["public_key_hex"], expected_digest, signature_value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign or verify SpiderVenomRegistry documents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign_parser = subparsers.add_parser("sign", help="Sign one or more registry json documents in place")
    sign_parser.add_argument("--keys", default=str(DEFAULT_KEYS_PATH))
    sign_parser.add_argument("--key-id", required=True)
    sign_parser.add_argument("--private-key", required=True)
    sign_parser.add_argument("paths", nargs="+")

    verify_parser = subparsers.add_parser("verify", help="Verify one or more registry json documents")
    verify_parser.add_argument("--keys", default=str(DEFAULT_KEYS_PATH))
    verify_parser.add_argument("paths", nargs="+")

    args = parser.parse_args()
    keys_path = pathlib.Path(args.keys).resolve()
    trusted_keys = load_trusted_keys(keys_path)

    if args.command == "sign":
        private_key = pathlib.Path(args.private_key).resolve()
        for raw_path in args.paths:
            path = pathlib.Path(raw_path).resolve()
            value = load_json(path)
            if not isinstance(value, dict):
                fail(f"{path}: expected object")
            sign_object(value, key_id=args.key_id, private_key_path=private_key, trusted_keys=trusted_keys, label=str(path))
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            print(f"signed registry document: {path}")
        return

    for raw_path in args.paths:
        path = pathlib.Path(raw_path).resolve()
        value = load_json(path)
        if not isinstance(value, dict):
            fail(f"{path}: expected object")
        verify_object(value, trusted_keys, str(path))
    print("registry signature verification ok")


if __name__ == "__main__":
    main()
