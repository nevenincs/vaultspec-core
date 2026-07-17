---
tags:
  - '#plan'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
tier: L1
related:
  - '[[2026-07-16-reference-topic-infix-adr]]'
  - '[[2026-07-16-reference-topic-infix-research]]'
---

# `reference-topic-infix` plan

## Description

This plan executes the reference-topic-infix decision (see related): topic-infix
scaffolding for the narrative document trio (audit, reference, research) through
the single filename builder, the CLI --topic flag, and the MCP create tool's
DocumentSpec, with firmware filename patterns and the generated CLI reference
updated in step. Omitted topic preserves current behavior byte-identically; adr,
plan, and exec never take an infix.

## Steps

- [x] `S01` - Add the optional topic parameter to create_vault_doc with the infixed filename for audit, reference, and research and a hard error for other types; `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `S02` - Add the --topic flag with shared-normalizer validation and non-admitting-type error to vault add; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `S03` - Add the optional topic field to DocumentSpec converging on the same create_vault_doc call; `src/vaultspec_core/mcp_server/tools/documents.py`.
- [x] `S04` - Add unit tests covering infixed filenames per admitting type, omitted-topic fallback, non-admitting-type error, normalization, and collision behavior; `src/vaultspec_core tests`.
- [x] `S05` - Document the infix form for the narrative trio in the firmware filename patterns and regenerate the bundled CLI reference; `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `S06` - Run the gates and open the PR closing the issue; `src/vaultspec_core`.

## Parallelization

S01 lands first (the builder is the shared authority); S02 and S03 then
parallelize over disjoint files; S04 and S05 follow implementation; S06 is last.

## Verification

- Infixed filename produced for each admitting type; omitted topic byte-identical.
- --topic on adr, plan, or exec exits with a hard error on both transports.
- Topic values normalize kebab-case through the shared normalizer.
- CLI reference drift test green after regeneration; prek and the unit gate pass.
- Code review audit passes; PR closes the issue.
