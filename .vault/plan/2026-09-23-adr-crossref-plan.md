---
tags:
  - '#plan'
  - '#adr-crossref'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-adr-crossref-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:d82dd44cda86eb46ee6d1e959b7c4ffe2e9329ba2f6123942374fc760731c55f'
---

# `adr-crossref` plan

Ship bounded ADR cross-referencing as a core backend with one CLI verb and one MCP tool, and adopt it in the ADR and curation workflows.

## Description

Approved 2026-09-23. Basis: the user authorised the whole feature in session on
2026-09-23 ("it's all yours to build and ship. deliver the full adr linking feature.
both the backend, with the adr, plans all preapproved; and the natural language
framework adjusted for the new workflow steps"), after requiring that no production path
run an unbounded judgment against the TypeSafe API.

The work implements `2026-09-23-adr-crossref-adr`, grounded in
`2026-09-23-adr-crossref-research`. Decision coverage: that ADR governs every Step; it
inherits `2026-09-23-typesafe-search-adr` unchanged, and its acceptance amends
`2026-07-09-mcp-tool-schema-adr` (hot-tool ceiling) and `2026-08-01-mcp-read-only-adr`
(restricted allowlist), recorded in S08. S02 extracts the link writer the ADR requires
both surfaces to share. The work runs on its own branch and worktree because a
concurrent session is editing the search package, the CLI and the firmware on
`feature/typesafe-search`; when that branch's environment-variable centralisation lands,
the crossref credential import moves to the config-layer resolver.

## Steps

- [x] `S01` - Record the prefilter evidence and the bounded cross-referencing decision; `.vault/research/2026-09-23-adr-crossref-research.md, .vault/adr/2026-09-23-adr-crossref-adr.md`.
- [x] `S02` - Extract the related-link writer from vault link add into core, under the document write lock with graph-cache invalidation; `src/vaultspec_core/vaultcore/related_links.py, src/vaultspec_core/cli/link_cmd.py`.
- [x] `S03` - Build the crossref backend - corpus, fingerprint, code stage, questions, engine, service and wire projection - with offline tests against the scripted provider; `src/vaultspec_core/crossref/`.
- [x] `S04` - Add the vault adr crossref CLI verb and regenerate the CLI reference and handbook; `src/vaultspec_core/cli/vault_crossref_cmd.py, docs/CLI.md, src/vaultspec_core/builtins/reference/cli.md`.
- [x] `S05` - Add the crossref MCP tool on both surfaces with the read-only argument guard, and ratchet the surface budget by its measured size; `src/vaultspec_core/mcp_server/tools/crossref.py, src/vaultspec_core/mcp_server/app.py, docs/MCP.md`.
- [ ] `S06` - Adopt the cross-reference step in the ADR and curation workflows and name the tool in the CLI rule and personas, then sync; `src/vaultspec_core/builtins/skills/, src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md, src/vaultspec_core/builtins/agents/`.
- [x] `S07` - Add the live cross-reference evaluation under the typesafe marker; `src/vaultspec_core/crossref/tests/test_live.py`.
- [ ] `S08` - Record the amendments to the tool-schema and read-only decisions and regenerate the feature index; `.vault/adr/2026-07-09-mcp-tool-schema-adr.md, .vault/adr/2026-08-01-mcp-read-only-adr.md`.
- [ ] `S09` - Review the integrated feature at plan close into the rolling audit; `.vault/audit/`.

## Parallelization

Sequential. S03 depends on S02's link writer; S04 and S05 render S03's result; S06 names
the surfaces S04 and S05 add; S08 records amendments that S05 makes true; S09 reviews the
whole.

## Verification

- The default test suite passes with no network and no key, including the crossref
  package's scripted-provider tests, the CLI and MCP surface tests, the tool-count and
  surface-budget ratchets, the reply-budget test, and the CLI reference and handbook
  drift tests.
- Lint and type checks pass on every touched file.
- The live evaluation (`-m typesafe`) ranks the planted governing ADR as a `link` and
  leaves the unrelated one out.
- A live run on this vault stays within the per-source ceiling of 46 evaluations and
  60 seconds.
- `vaultspec-core vault check all` is clean for the feature, and the plan-close review in
  S09 passes.
