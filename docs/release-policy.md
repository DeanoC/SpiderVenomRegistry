# Release Policy

SpiderVenomRegistry publishes signed static registry documents for the matching
SpiderVenoms release line.

## Versioning

- Registry tags use `vX.Y.Z`
- The default expectation is that the registry tag matches the SpiderVenoms
  release version it was generated from
- In practice, registry `v0.5.8` should be generated from SpiderVenoms
  `v0.5.8`

## Release inputs

The release workflow consumes these published SpiderVenoms assets:

- `spidervenoms-release-facts.json`
- one managed-bundle archive, currently
  `spidervenoms-managed-local-linux-x86_64.tar.gz`

The release facts provide:

- bundle id
- release version
- package ids
- per-platform artifact URLs
- per-platform sha256 checksums
- published timestamp

The bundle archive is used to extract and verify the signed in-bundle
`release.json` before registry generation.

## Release outputs

Registry releases publish:

- the signed `v1/` tree
- `keys/trusted-registry-keys.json`
- `spidervenom-registry-v1.tar.gz`
- `spidervenom-registry-v1.tar.gz.sha256`

The same generated tree is suitable for static hosting, including GitHub Pages.

## Signing

- Registry documents are signed with a dedicated registry signing key
- Bundle signing keys and registry signing keys are separate trust stores
- The release workflow expects a secret named
  `SPIDERVENOMREGISTRY_PRIVATE_KEY_PEM`

## Local maintainer flow

Generate the registry locally:

```bash
python3 ./scripts/generate_registry.py \
  --spidervenoms-root ../SpiderVenoms \
  --private-key ./keys/private/spidervenomregistry-dev-2026-03.pem
```

Validate it:

```bash
bash ./scripts/check-registry.sh
```

Package it for static hosting:

```bash
bash ./scripts/package-registry-site.sh --out-dir ./dist
```
