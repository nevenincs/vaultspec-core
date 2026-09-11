---
tags:
  - '#plan'
  - '#binary-release-bundles'
date: '2026-09-11'
tier: L1
related:
  - '[[2026-09-11-binary-release-bundles-adr]]'
  - '[[2026-09-11-binary-release-bundles-bundle-contract-research]]'
  - '[[2026-09-11-binary-release-bundles-current-pipeline-reference]]'
modified: '2026-09-11'
body_schema: body-v2
body_hash: 'sha256:ec3578ddffc3183145389526f1c90bd78e7f33be182e0a90441a308a78aca567'
---

# `binary-release-bundles` plan

## Description

Approved 2026-09-11
Advance authorization basis: the user explicitly authorized autonomous ADR, planning, execution, and final review in this request.
Implement the accepted target-archive contract across build packaging, release publication, channels, verification, and direct-download guidance. Decision coverage is supplied by `2026-09-11-binary-release-bundles-adr`; its research and code reference are inherited.

## Steps

- [x] `S01` - Introduce the target bundle contract and generated metadata.; `dev`.
- [x] `S02` - Publish only validated bundles through release channels.; `.github/workflows/binaries.yml`.
- [x] `S03` - Cover the public surface with tests and direct-download guidance.; `docs/channels.md`.

## Parallelization

Steps run in order: S01 establishes the artifact contract, S02 consumes it in publication, and S03 closes the public verification surface.

## Verification

Build, extraction, metadata, target coverage, channel, documentation, and project checks pass; every Step is closed; the final integrated review passes.
