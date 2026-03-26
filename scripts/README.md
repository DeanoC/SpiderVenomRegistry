# Scripts

Registry generator:

```bash
python3 ./scripts/generate_registry.py \
  --spidervenoms-root ../SpiderVenoms \
  --private-key ./keys/private/spidervenomregistry-dev-2026-03.pem
```

Registry validation:

```bash
bash ./scripts/check-registry.sh
```

Static site packaging:

```bash
bash ./scripts/package-registry-site.sh --out-dir ./dist
```

See [../docs/release-policy.md](/Users/deanocalver/Documents/Projects/Spider/SpiderVenomRegistry/docs/release-policy.md)
for the release flow.
