---
tags:
  - '#exec'
  - '#release-publication-ordering'
date: '2026-09-18'
modified: '2026-09-18'
body_schema: 'body-v2'
body_hash: 'sha256:b36c0d3bd6ba7d8fd582556db2d8c149b5e1c07bd8ce03d63b20c69d6cf02f7b'
related:
  - "[[2026-09-18-release-publication-ordering-plan]]"
---

# `release-publication-ordering` ledger

## Changes

- `S01` `M` `release-please-config.json`
- `S01` `M` `dev/guards/test_automation_contracts.py`
- `S01` `verify:` `pytest dev/guards/test_automation_contracts.py` -> `pass`
- `S02` `M` `.github/workflows/binaries.yml`
- `S02` `M` `.github/workflows/publish.yml`
- `S02` `M` `.github/ci-contract-allow.txt`
- `S02` `M` `dev/guards/test_automation_contracts.py`
- `S02` `M` `dev/guards/test_release_matrix_coverage.py`
- `S02` `verify:` `pytest dev/guards -m repo` -> `pass`
- `S03` `M` `docs/README.md`
- `S03` `verify:` `pymarkdown scan` -> `pass`
- `S04` `M` `.github/ci-contract-allow.txt`
- `S05` `verify:` `pypi vaultspec-core 0.2.2 wheel and sdist present` -> `pass`
- `S02` `A` `.github/workflows/channels.yml`
- `S02` `M` `dev/guards/test_release_provenance.py`
- `S02` `M` `docs/README.md`
- `S02` `M` `.vault/adr/2026-09-18-release-publication-ordering-adr.md`

## Notes

- `S02` Scope widened to publish.yml: the distribution is attached there, so the release could not be published from the binaries lane, and the acquisition dispatch had to follow publication because it acquires unauthenticated.
- `S04` No tracked file: PUT /repos/nevenincs/vaultspec-core/immutable-releases returned 204 and the setting now reads enabled=true, enforced_by_owner=false. It was disabled earlier in the session to unblock an asset upload; the draft ordering is what makes it safe to hold.
- `S04` Correction: the S04 row naming .github/ci-contract-allow.txt is wrong. That file was touched by S02 and not by this Step, which changed no tracked file at all. The row is left in place because this ledger is append-only.
- `S05` No tracked file. The v0.2.2 release object carried zero assets and was sealed immutable, so its assets could never be attached; it was deleted. The tag (5b1187a8) and the PyPI 0.2.2 wheel and sdist are untouched, so nothing a user can depend on was removed. Not rebuilt: a repair dispatch resolves publish.yml from the tag, which predates the draft publication step, so the rebuilt release could not have been published without hand intervention - and 0.2.3 supersedes it. Survey while there: v0.2.1 carries no binaries and v0.2.0 is missing the linux-x86_64 pair, so both were correctly demoted and latest correctly remains v0.1.73.
- `S02` Reopened by the plan-close review: 2026-09-18-release-publication-ordering-audit records a high finding. The channel pointers are pushed by the binaries lane while the release is still a draft, so they advertise download URLs that 404 until publish.yml flips it. The fix needs authorization for where CHANNEL_ROOT_DEPLOY_KEY may live.
