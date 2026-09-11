---
tags:
  - '#exec'
  - '#binary-release-bundles'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:b53e6c901a25b6d8f7f3533fa90d34e2847fdd49fd77bba6b0505661a16140a2'
related:
  - "[[2026-09-11-binary-release-bundles-plan]]"
---

# `binary-release-bundles` ledger

## Changes

- `S01` `A` `dev/packaging/bundles.py`
- `S01` `A` `dev/packaging/tests/test_bundles.py`
- `S01` `M` `dev/binaries/build_pyapp.py`
- `S01` `M` `dev/binaries/tests/test_windows_icon.py`
- `S01` `M` `dev/binaries/windows_icon.py`
- `S01` `M` `dev/packaging/products.py`
- `S01` `M` `justfile`
- `S01` `T` `dev`
- `S02` `T` `.github/workflows/binaries.yml`
- `S03` `T` `docs/channels.md`
- `S02` `M` `.github/workflows/binaries.yml`
- `S02` `M` `.github/ci-contract-allow.txt`
- `S02` `M` `dev/packaging/bundles.py`
- `S02` `M` `dev/packaging/generate.py`
- `S02` `M` `dev/packaging/homebrew.py`
- `S02` `M` `dev/packaging/products.py`
- `S02` `M` `dev/packaging/scoop.py`
- `S02` `M` `dev/packaging/validate.py`
- `S02` `M` `dev/packaging/tests/test_bundles.py`
- `S02` `M` `dev/packaging/tests/test_generators.py`
- `S02` `M` `dev/packaging/tests/test_validate.py`
- `S03` `M` `docs/channels.md`
- `S03` `M` `dev/packaging/tests/test_bundles.py`
- `S02` `M` `.github/workflows/acquisition.yml`
- `S03` `M` `dev/guards/test_release_matrix_coverage.py`
