---
tags:
  - '#adr'
  - '#curator-reframe'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-06-28-curator-reframe-research]]"
---

# `curator-reframe` adr: `canonical ADR status taxonomy and reconciliation curator` | (**status:** `accepted`)

## Problem Statement

The `vaultspec-curate` skill and `vaultspec-docs-curator` agent have been reframed from a
mechanical `.vault/` schema janitor into an ADR architecture semantic reconciliation
persona, because the CLI now owns mechanical hygiene. The reframed curator's core job is
to enforce that every ADR carries a correct, canonical status and that supersession is
propagated. But the status taxonomy it must enforce is not encoded anywhere in the
library. Status is free text in the document body H1; `DocumentMetadata` models
`supersedes` and `superseded_by` but has no `status` field; `core/enums.py` has no status
enum; and no `vault check` validates status. Worse, the taxonomy is self-contradictory
across its only two expressions: the ADR template comment declares the set
`proposed | accepted | rejected | deprecated`, while `adr_supersede` writes the literal
`superseded`, a value absent from that set. A curator cannot enforce a taxonomy the
library does not define. This ADR records the decision to encode the canonical status
taxonomy as a single source of truth in the core library and to add the mechanical
validator that backs the curator.

## Considerations

The corpus is 82 ADRs with at least three status encodings: the canonical token in the
body H1 (a backtick-quoted status value such as `accepted` after the title), a legacy
`## Status` section with a bare value, and one table form. Roughly 68 are `accepted`, 5
`proposed`,
and none are `superseded` or `deprecated` despite the lifecycle existing. The existing
mechanical surface is established: `DocumentMetadata` in
`src/vaultspec_core/vaultcore/models.py` carries the supersession edges; `adr_supersede`
in `src/vaultspec_core/core/adr.py` is the one status writer and rewrites the H1 token to
`superseded` only when it matches the H1-inline regex; and the check suite in
`src/vaultspec_core/vaultcore/checks/` exposes the `CheckResult` / `CheckDiagnostic` /
`Severity` contract in `_base.py`, re-exports each checker through `__init__.py`,
aggregates via `run_all_checks`, and surfaces under the `vault check` CLI group. The
status set must remain expressible in the body H1, where status semantically belongs, not
forced into frontmatter.

## Considered options

- Prose-only taxonomy in the skill references. Rejected: the curator would enforce a set
  the library never defines, so drift and the template-versus-tool contradiction persist
  and nothing validates the 82 existing ADRs.
- Encode the canonical status enum in the core library as the source of truth, reconcile
  the template and the supersede tool to it, and add an `adr-status` check. Chosen: gives
  the curator a real contract to enforce and a mechanical backstop.
- Migrate status into frontmatter and model it on `DocumentMetadata`. Rejected: status is
  a human-facing body concept tied to the H1; a frontmatter migration rewrites every ADR,
  breaks the template heading contract, and duplicates state already shown in the body.

## Constraints

Status lives in the body H1, not frontmatter, so the enum is a validation vocabulary and
a writer constant, not a metadata field. The change must not break the 82 existing ADRs:
the validator surfaces legacy encodings as warnings to normalize, not hard failures that
block the suite. `adr_supersede`'s H1 regex cannot rewrite the legacy `## Status` form, so
those remain a known normalization gap the curator handles. Work must pass the unit gate
(`pytest -m unit`) with factory-based, real-filesystem tests and no mocks, skips, or
stubs.

## Implementation

A single `AdrStatus` string enum is added to the core library as the canonical set:
`proposed`, `accepted`, `rejected`, `superseded`, `deprecated`. `superseded` names a
decision replaced by a specific successor ADR (and carries `superseded_by`); `deprecated`
names a decision retired without a direct successor. The ADR template's status-convention
comment and H1 placeholder are reconciled to this set, and `adr_supersede` writes the
enum's `superseded` value rather than a bare literal. A new `adr-status` checker parses
each ADR's H1 (and detects the legacy `## Status` section) and validates the token against
the enum, flagging off-taxonomy or missing values, non-canonical encodings, and
frontmatter-versus-body supersession divergence (a `superseded_by` set while the body
status was never rewritten). It is registered in the checks `__init__`, included in
`run_all_checks`, and surfaced as `vault check adr-status` with the standard `--fix`,
`--feature`, and `--json` options, where `--fix` applies only the safe normalizations.
The `vaultspec-curate` skill references are finalized to treat the validator as present
rather than forthcoming. The detailed encodings and divergence rules are carried in the
skill's `adr-status-taxonomy.md` reference, which mirrors the enum.

## Rationale

Encoding the set in code is the only option under which the curator's enforcement is
meaningful: the skill, the template, the supersede tool, and the validator all derive
from one definition rather than three contradictory prose statements. The
`superseded`-versus-`deprecated` split is retained because the two lifecycle ends differ
materially - replacement by a named successor versus retirement without one - and the
supersede tool already commits the project to `superseded`. The research artifact records
the corpus measurements and the discovery grounding behind these choices.

## Consequences

The curator gains a contract it can enforce and a mechanical backstop, and the corpus
gains a validated status lifecycle that the status rollup and future lifecycle reporting
can trust. The cost is real: the 10 legacy `## Status` ADRs and the bare-token and table
forms need normalization, and the `adr_supersede` regex still cannot rewrite the
`## Status` form, so the curator must correct those bodies through the CLI mutators. The
enum and the template must be kept in lockstep; a future status value added in one place
without the other reintroduces exactly the contradiction this ADR removes.
