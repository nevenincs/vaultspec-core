---
tags:
  - '#research'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-16-reference-topic-infix-adr]]"
---

# `adr-topic-infix` research: `same-day ADR disambiguation`

The question is whether an ADR may use the existing topic-infix mechanism when
one feature needs several independently searchable decisions on the same date.
The current creator rejects that shape even though the framework's plan guidance
allows a plan to execute a cluster of ADRs. The evidence favors extending the
existing infix mechanism to ADRs while retaining the exclusions that are tied to
machine-derived execution records and a single plan cluster; the ADR must settle
that revised cardinality boundary.

## Findings

### The current restriction creates the reported collision

`_TOPIC_INFIX_TYPES` admits audit, reference, and research only, and
`create_vault_doc` refuses a topic for every other type before it constructs
the target filename. A second same-day ADR consequently resolves to the same
`{date}-{feature}-adr.md` target and the normal existence guard rejects it.
The CLI and MCP apply the same three-type admission check before calling that
shared creator, so the defect occurs on both supported transports.
`src/vaultspec_core/vaultcore/hydration.py:44-48`
`src/vaultspec_core/vaultcore/hydration.py:431-433`
`src/vaultspec_core/cli/vault_cmd.py:258-272`
`src/vaultspec_core/mcp_server/tools/documents.py:275-295`

### The former ADR boundary conflicts with the framework's current planning model

The 2026-07-16 topic-infix ADR excluded ADRs on the premise that cardinality
rules require an amend-or-supersede path. Its own related plan model and the
current vault rules instead distinguish one ADR per decision from a plan that
executes a cluster of ADRs. Separate decisions arising from the same research
therefore need separate records without being forced into separate feature tags
or inaccurate dates. The prior record should be superseded rather than silently
contradicted. `.vault/adr/2026-07-16-reference-topic-infix-adr.md:20-33`
`.vaultspec/rules/vaultspec-system.builtin.md:96-100`

### Existing mechanics already preserve identifier and collision safety

When an admitted topic is supplied, the creator uses
`{date}-{feature}-{topic}-{type}.md`; it preserves the omitted-topic filename,
normalizes topics at both transport boundaries, and rejects duplicate paths and
cross-directory stem collisions. The existing tests prove two same-day topic
values can coexist while a duplicate fails. Extending the admission set changes
no filename algorithm or collision authority. `src/vaultspec_core/vaultcore/hydration.py:457-510`
`src/vaultspec_core/vaultcore/tests/test_hydration.py:455-555`

### The viable alternatives differ in record fidelity

Keeping the rejection would require changing the cluster guidance or accepting
feature-tag splitting and postdated records; neither preserves the stated
one-decision-per-record model. Allowing all document types is broader than the
evidence: plan documents remain one execution cluster and exec filenames remain
derived from plan identifiers. Admitting ADRs alongside the narrative trio is
the narrow option; whether ADR filenames should still be called narrative is a
terminology follow-up, not an implementation blocker.

## Sources

- `src/vaultspec_core/vaultcore/hydration.py:44-48`
- `src/vaultspec_core/vaultcore/hydration.py:431-510`
- `src/vaultspec_core/cli/vault_cmd.py:258-272`
- `src/vaultspec_core/mcp_server/tools/documents.py:275-295`
- `src/vaultspec_core/vaultcore/tests/test_hydration.py:455-555`
- `.vault/adr/2026-07-16-reference-topic-infix-adr.md:20-109`
- `.vaultspec/rules/vaultspec-system.builtin.md:96-100`
- https://github.com/nevenincs/vaultspec-core/issues/266
