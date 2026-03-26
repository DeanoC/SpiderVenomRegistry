# SpiderVenomRegistry V1

`SpiderVenomRegistry` publishes static signed discovery documents for
bundle-first venom releases.

Document types:

- `v1/index.json`
- `v1/channels/<channel>.json`
- `v1/bundles/<bundle_id>/<release_version>.json`

Trust model:

- each registry document carries `digest` + `signature`
- registry trust is separate from bundle trust
- consumers must verify:
  - registry document signatures
  - bundle archive checksum
  - signed in-bundle `release.json`
  - signed manifest templates

V1 is read-only:

- no host check-in
- no rollout cohorts
- no auto-apply update behavior

