---
tags:
  - '#plan'
  - '#discovery-fallback'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-typesafe-search-adr]]'
  - '[[2026-08-26-rag-search-exposure-adr]]'
  - '[[2026-06-10-cli-reference-automation-adr]]'
  - '[[2026-07-09-firmware-mcp-primacy-adr]]'
  - '[[2026-05-17-cli-json-consistency-adr]]'
  - '[[2026-09-23-typesafe-search-audit]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:20b86eac31edaa64612aafe6a52c9bca4e3cfc6e0b94cc268b64f1804bf45248'
---

# `discovery-fallback` plan

Backend-resolved search fallback, CLI and MCP parity, and state-free discovery guidance.

## Description

Approved 2026-09-23. The user reviewed the audit findings in session and approved the
direction, adding "ensure the CLI and MCP have parity and all capability is derived
from the backend, not business logic in CLI and MCP", then delegated full execution
("all yours").

Follow-up to the typesafe-search feature. It is filed under its own feature tag
because that feature's plan stem is taken. The work is governed by
`2026-09-23-typesafe-search-adr` and its discovery-fallback amendment note, whose
evidence is `2026-09-23-typesafe-search-audit` (search-degradation, guidance-gate,
output-handling, surface-drift, user-docs). Scope by Step:

- S01: the amendment's backend-resolved fallback and thin surfaces.
  `2026-08-26-rag-search-exposure-adr` holds unchanged: core reads the companion
  probe's provisioning, calls no rag API and returns no rag content.
  `2026-05-17-cli-json-consistency-adr` governs the CLI `--json` shape.
- S02 and S04: the amendment's state-free guidance and the retained ADR listing.
  `2026-07-09-firmware-mcp-primacy-adr` forbids conditional firmware logic and keeps
  guidance capability-worded; rag-search-exposure keeps one discovery vocabulary.
- S03: `2026-06-10-cli-reference-automation-adr`; the reference changes only through
  the generator.
- S05 and S06: the amended ADR as a whole.

No new costly decision is involved beyond the amendment.

## Steps

- [x] `S01` - Resolve the search degradation next step in the backend from companion detection and the requested record types, render the CLI and MCP search and status surfaces from one backend result with identical fields (fixing the answered drift), move search and status decision logic out of cli/ and mcp_server/, and test it; `src/vaultspec_core/search/, src/vaultspec_core/core/diagnosis/, src/vaultspec_core/cli/vault_search_cmd.py, src/vaultspec_core/cli/status_cmd.py, src/vaultspec_core/mcp_server/tools/search.py, src/vaultspec_core/mcp_server/tools/orientation.py`.
- [x] `S02` - Replace the status-gated routing constant with state-free wording and update the builtins-sync guard tests; `src/vaultspec_core/core/discovery_guidance.py, src/vaultspec_core/tests/test_discovery_guidance.py`.
- [x] `S03` - Fix the reference generator inputs so the bundled CLI reference and docs/CLI.md list the real hit fields and render the vault search options table, then regenerate; `src/vaultspec_core/cli/reference_gen.py, src/vaultspec_core/builtins/reference/cli.md, docs/CLI.md`.
- [x] `S04` - Rewrite the bundled discovery guidance with single-home routing, search output handling, the unavailable branch and a degraded-mode grep carve-out, add a coverage-check method to the ADR skill and code-reviewer, then sync; `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md, src/vaultspec_core/builtins/skills/vaultspec-code-research/, src/vaultspec_core/builtins/skills/vaultspec-curate/, src/vaultspec_core/builtins/skills/vaultspec-adr/, src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md, src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`.
- [x] `S05` - Add hosted search and the degradation chain to the user discovery narrative and align the CLI and MCP remediation wording; `README.md, docs/framework.md, docs/CLI.md, docs/MCP.md`.
- [ ] `S06` - Review the plan's changes against the amended ADR and append the findings to the rolling audit; `.vault/audit/2026-09-23-typesafe-search-audit.md`.

## Parallelization

S01, S02 and S03 run in sequence: S02 words the guidance against S01's result fields,
and S03 renders S01's fields into the reference. After S03, S04 (builtins and sync) and
S05 (user docs) may run concurrently; their files are disjoint. S06 runs last on the
stable set.

## Verification

- With no key, and with a failing service, CLI `--json` and MCP `search` return the
  same fields, including `answered` and a typed next step. The next step names a rag
  vault search over the requested types when the companion is provisioned, and
  `find` or `vault list` plus grep when it is not.
- `cli/` and `mcp_server/` hold no search or status branching beyond rendering.
- No builtin conditions routing on `status`; the guidance guard tests pass.
- The reference drift check passes, and the reference lists the wire hit fields and
  the vault search options table.
- `just check-python`, the type checks, `check-markdown` and the test suite pass.
- The S06 review against the amended ADR passes.
