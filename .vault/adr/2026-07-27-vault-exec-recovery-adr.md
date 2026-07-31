---
tags:
  - '#adr'
  - '#vault-exec-recovery'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:363046fc4a8b5f9c2c92cc0217f36bc74fff10cdd536e7146897ff5ec30b0732'
related:
  - "[[2026-07-27-vault-exec-recovery-research]]"
---

# `vault-exec-recovery` adr: `explicit recovery ownership for historical execution mappings` | (**status:** `accepted`)

## Problem Statement

`vault check exec-mapping` correctly reports execution records whose `step_id` no longer identifies a live parent-plan Step, but it intentionally has no mutation authority. The verified recovery set contains records that can be truthfully re-linked, a historical record whose Step is retired, and prose-era records for which no formal Step exists. These need explicit, auditable operator actions rather than a checker-side guess, as grounded in `2026-07-27-vault-exec-recovery-research` and bounded by `2026-07-23-vault-check-validators-adr`.

## Considerations

- A display-path-looking value is not the canonical `S##` identity the validator and plan parser use; only resolution against the recordâ€™s actual parent plan can establish a safe replacement.
- Retired Step identities and legacy records without `step_id` already have distinct validator meanings. Recovery must preserve those meanings rather than make the checker permissive.
- Execution bodies are historical evidence. Recovery changes only machine-owned metadata or archives the complete record; it does not rewrite authored prose.
- The CLI already establishes atomic mutation, dry-run, no-op, and stable JSON conventions suitable for an operator-owned recovery surface.

## Considered options

- **Dedicated `vault exec` recovery commands (chosen).** Explicit commands classify and apply one verified recovery at a time, with validation before mutation and an auditable result.
- **`vault check exec-mapping --fix`.** Rejected: the checker cannot safely infer whether a malformed value denotes a live Step, a retired historical record, or an unmappable legacy record.
- **Bulk metadata migration.** Rejected: superficially similar values have different provenance; bulk rewriting could mis-link historical evidence.
- **Relax the validator for malformed values.** Rejected: it would conceal corruption and collapse the distinction between a valid legacy record and an invalid claimed mapping.
- **Hand-edit frontmatter or archive paths.** Rejected: bypasses validation, atomicity, output conventions, and preservation guarantees.

## Constraints

- The accepted validator remains read-only with its live, retired, dangling, archived-parent, and no-`step_id` classifications unchanged.
- `relink` writes only after resolving a supplied target against the record's existing, live, parseable parent plan; it rejects absent, retired, ambiguous, or cross-plan targets.
- Recovery does not create a parent relationship, alter `related:`, mutate tags or dates, normalize the body, or infer a target from prose.
- Mutations are atomic, support dry-run and JSON output, report no-ops explicitly, and preserve the original body bytes.
- `retire` is limited to a record whose current identity is in the parent planâ€™s retired ledger. `detach` is limited to a claim resolving to neither a live nor retired Step.

## Implementation

Introduce a `vault exec` command group with `relink`, `retire`, and `detach` operations. They share typed recovery helpers beneath thin CLI wrappers, validate the exec document and its related parent plan, parse the plan once, preserve authored body content byte-for-byte, and use atomic writes or an atomic archive move. The initial recovery applies relink only to verified-live records, retire to the verified retired-Step record, and detach to verified prose-era legacy records.

## Rationale

Recovery is semantic, not syntactic. The resolver can prove a supplied target is live in the recordâ€™s existing parent plan, making canonical re-linking safe; it cannot prove intent for a retired or prose-era record. Retiring the former preserves evidence while placing it outside active validation. Detaching the latter records the only truthful machine state: no formal Step anchor.

Keeping the validator strict identifies future dangling or retired claims while leaving recovery authority with an operator who supplies historical judgment. This preserves the boundary established by `2026-07-23-vault-check-validators-adr` while providing the missing mutation surface.

## Consequences

The verified historical set can converge without inventing mappings, losing evidence, or weakening validation. New repairs are canonical and mechanically verifiable; retirement and detachment become explicit, reviewable operations. Records that cannot satisfy a command precondition remain visible findings.
