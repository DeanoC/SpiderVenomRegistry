# SpiderVenomRegistry

Static signed registry metadata for discovering published Spider venom bundles.

Current scope:

- read-only `v1/` registry documents
- signed registry index, channel manifests, and bundle release manifests
- generation tooling that projects published `SpiderVenoms` bundle releases into
  a bundle-first registry catalog

This repo is intentionally service-free in v1. It is meant to be hostable from
any static HTTPS origin.

## Registry layout

- `v1/index.json`
- `v1/channels/<channel>.json`
- `v1/bundles/<bundle_id>/<release_version>.json`

## Maintainer flow

Generate or refresh the registry from local `SpiderVenoms` release metadata:

```bash
python3 ./scripts/generate_registry.py \
  --spidervenoms-root ../SpiderVenoms \
  --private-key ./keys/private/spidervenomregistry-dev-2026-03.pem
```

Validate the generated registry:

```bash
bash ./scripts/check-registry.sh
```

Package it for static hosting:

```bash
bash ./scripts/package-registry-site.sh --out-dir ./dist
```

Tagged releases are intended to:

- download `spidervenoms-release-facts.json` from the matching `SpiderVenoms` release
- extract the signed `release.json` from a published managed bundle archive
- regenerate and sign the `v1/` tree
- publish the static registry tree for GitHub Pages and release assets

See [docs/release-policy.md](/Users/deanocalver/Documents/Projects/Spider/SpiderVenomRegistry/docs/release-policy.md).
