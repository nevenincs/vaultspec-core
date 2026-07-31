---
tags:
  - '#reference'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:e195790f9482021c6d619a321e316c2306871dd6126cbdf9e7fcf369eccf6725'
related:
  - "[[2026-07-27-adr-topic-infix-research]]"
  - "[[2026-07-16-reference-topic-infix-adr]]"
---

# `adr-topic-infix` reference: `ADR topic-infix creation path`

This reference maps the one admission rule through the creator, CLI, MCP, tests,
and generated user-facing rule text. It is based on the current worktree at
`4c02b95b905bc85f127d4d1cd88d0a6e4ae625b6`.

## Summary

`src/vaultspec_core/vaultcore/hydration.py:44-48` owns the admitting document
types in `_TOPIC_INFIX_TYPES`; `create_vault_doc` validates the set at
`hydration.py:431-435` and builds the infixed filename at `hydration.py:498-500`.
Changing this set to include `DocType.ADR` is the source-of-truth change. The
existing no-topic path and duplicate/stem-collision protections must remain
unchanged.

`src/vaultspec_core/cli/vault_cmd.py:101-110` publishes the `--topic` help text,
and `vault_cmd.py:258-272` repeats the admission set before normalization. Its
wording and guard must admit ADRs so the CLI remains aligned with the creator.

`src/vaultspec_core/mcp_server/tools/documents.py:133-147` documents the schema
field, while `documents.py:275-295` validates it and calls the same creator.
Its type guard and error wording must use the same four-type set as the CLI and
creator; no new MCP field or alternate filename builder is needed.

`src/vaultspec_core/vaultcore/tests/test_hydration.py:455-555` is the direct
creator regression suite. It should add ADR to the admitting parametrization,
remove ADR from the rejection parametrization, and exercise two same-day ADR
topics plus duplicate rejection. `tests/unit/mcp_server/test_create_tool.py:147-202`
should replace the rejected-ADR and mixed-batch expectations with successful
ADR-topic creation. A real CLI test belongs with the existing `vault add` tests
so CLI parsing, normalization, and the shared creator run together.

The vocabulary must be updated wherever it claims the infix is available only
to audit, reference, and research: `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`,
`.vaultspec/rules/vaultspec.builtin.md`, and the generated CLI reference. The
source rule is the authored built-in; generated mirrors are refreshed through
the project's owning sync/generation path, never hand-edited.
