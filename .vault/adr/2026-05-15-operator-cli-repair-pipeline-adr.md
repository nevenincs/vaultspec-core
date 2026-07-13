---
tags:
  - '#adr'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
modified: '2026-06-13'
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-research]]'
  - '[[2026-05-15-operator-cli-repair-pipeline-audit]]'
  - '[[2026-05-15-operator-cli-repair-pipeline-reference]]'
---

# `operator-cli-repair-pipeline` adr: `explicit vault repair pipeline` | (**status:** `proposed`)

## Problem Statement

`vaultspec-core vault check all --fix` is useful but too ambiguous for degraded
vault recovery. It combines diagnosis and partial mutation without making the
operator lifecycle explicit. It does not rebuild feature indexes, does not
separate authorial traceability gaps from mechanical repairs, and can leave
later checks using graph state built before earlier mutations.

## Considerations

Option 1: keep expanding `vaultspec-core vault check all --fix`.

This preserves the current surface but deepens the ambiguity. Some checks are
diagnostic-only, generated indexes remain separate, and operators still need to
infer when to rerun validation.

Option 2: add a dedicated vault repair pipeline.

This makes recovery a first-class workflow while preserving existing check
commands. The pipeline can expose phases, dry-run output, changed files,
generated index decisions, post-fix checks, unresolved findings, and manual
next actions.

Option 3: repurpose `vaultspec-core spec doctor`.

This is rejected because `spec doctor` checks framework/provider health, not
`.vault/` content integrity.

## Constraints

- Existing scripted users may rely on `vaultspec-core vault check all --fix`.
- Generated feature indexes are lifecycle artifacts, not user-authored docs.
- Index relocation belongs to migrations and lazy first-use registry behavior.
- Windows and macOS default filesystem behavior is case-insensitive but
  case-preserving.
- Human output and JSON output must stay aligned.
- Tests must exercise real behavior and must not depend on fakes or shortcuts.

## Implementation

Adopt Option 2: design and implement a dedicated repair pipeline command.

Preferred command:

```text
vaultspec-core vault repair
```

The command should orchestrate:

1. `preflight`: detect platform, migration, and dirty generated-artifact risks.
1. `check`: run diagnostics and group root causes.
1. `fix`: apply safe mechanical fixes transactionally.
1. `index`: rebuild or queue generated feature indexes affected by mutation.
1. `postcheck`: rebuild graph state and rerun relevant checks.
1. `summary`: report changed files, unresolved diagnostics, and next actions.

Initial options:

```text
vaultspec-core vault repair --dry-run
vaultspec-core vault repair --json
vaultspec-core vault repair --include-index
vaultspec-core vault repair --no-index
vaultspec-core vault repair --verbose
```

`vaultspec-core vault check all --fix` remains a compatibility surface and a
check-level fixer. It should not be documented as the complete repair workflow.

## Rationale

The operator need is not merely "run checks and fix what can be fixed." The
operator need is "make the vault internally consistent and policy-compliant
without hidden side effects." A dedicated repair command matches the workflow
shape: platform-aware preflight, safe mutation, generated artifact refresh,
post-fix validation, and actionable unresolved work.

This design follows current CLI guidance: human-first output, explicit state
changes, structured JSON for automation, and command semantics that avoid
quietly expanding an existing option after users may have scripted it.

## Consequences

Positive consequences:

- Operators can distinguish diagnostics from repair.
- Mechanical, generated, and authorial work can be reported separately.
- Post-fix validation becomes part of the command contract.
- Windows case-only path risk has a natural home in preflight and fix planning.
- Existing `vault check` commands remain useful and scriptable.

Trade-offs:

- The CLI gains a new command surface.
- Repair orchestration needs tests across graph, index, migration, and path
  behavior.
- Some traceability gaps will remain manual by design, so output must make that
  boundary explicit.
