---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:4586aa1f06a705f89c6cf96167011a9a3f550cbdb30bf63b14b9554cfa37c85f'
step_id: 'S17'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Run test_committed_reference_is_in_sync_with_live_surface and confirm it stays green, proving only prose outside the markers changed

## Scope

- `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`

## Description

- Ran the generated-reference byte-fidelity suite and the drift guard; both green.
- Confirmed `test_committed_reference_is_in_sync_with_live_surface` passes, proving only prose outside the markers changed and the committed reference equals fresh generator output.
- Ran the unit guard filtered to reference, drift, and builtin coverage as a wider safety net.

## Outcome

The generated and drift suites pass 22 of 22, including the in-sync byte-fidelity assertion. The unit guard passes 57 of 57. Lint, type-check, and spec doctor are clean. The change is confined to header prose; the gateway catalog is byte-stable.

## Notes

The byte-fidelity and drift tests are marked integration, so they run outside the `-m unit` gate; both suites were run explicitly. No skips, no mocks.
