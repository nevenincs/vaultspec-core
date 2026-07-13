---
tags:
  - '#research'
  - '#cli-surface-consolidation'
date: '2026-05-17'
modified: '2026-06-13'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-surface-consolidation` research: `Two-surface CRUD: spec sync duplicates top-level sync`

Synthesis note for findings S12, S13, and round-1 finding [13]
(`vault sanitize annotations` overlaps with `vault check annotations --fix`).

## Findings

### S12 — `spec rules sync` rejects the provider positional that top-level `sync` requires

Joan round-3a finding [49]. Two surfaces invoke the same
conceptual operation (push spec content out to enrolled
providers):

- `vaultspec-core sync claude` succeeds; `claude` is the
  documented provider positional.
- `vaultspec-core spec rules sync claude` fails with exit
  code 2. The granular form rejects the positional the
  top-level form requires.

Same verb (`sync`), two incompatible argument schemas
depending on whether the user reached the granular noun-
group form or the top-level form. There is no `--help` text
that reconciles them.

### S13 — `spec * sync` duplicates a slice of top-level `sync`

Joan round-3a finding [50]. For every noun group `g` in
`{rules, skills, agents, system, mcps}`,
`vaultspec-core spec g sync` produces output overlapping
significantly with `vaultspec-core sync`. The relationship
between the granular and the global surface is unstated. A
pre-commit author has no signal whether to call the global
form or the per-group form.

### Round-1 finding [13] — `sanitize` overlaps with `check ... --fix`

`vault sanitize annotations` "strips generated template
annotations from vault documents". `vault check annotations --fix` does the same; the `check`-help calls the `--fix`
flag "strip generated template annotations". Both accept the
same flags. Both produce the same output. Two different
verbs reach the same destination.

`vault sanitize` is a group of one. Its sibling group
`vault check annotations` has the same effect via `--fix`.
The two surfaces have feature parity by accident.

### The pattern across the three findings

Three places where the same operation can be reached through
two different command paths. In each case the duplication
appears to have grown organically — at some point a granular
form was added without retiring or reconciling the global
form (or vice versa).

The cost is twofold: doubled documentation burden, and a
real user-facing inconsistency when the two surfaces drift
(as S12 already shows — different positional arguments
accepted).

### What consolidation should look like

For each duplicate pair, pick one canonical surface and
deprecate the other:

- **`spec * sync` vs `sync`.** Pick the granular form
  (`spec rules sync`, `spec skills sync`, etc.) as
  canonical because it lets the operator scope the sync
  precisely. Top-level `sync` becomes a fanout helper
  that calls each granular form, documented as
  equivalent to running them all.
- **`vault sanitize annotations` vs `vault check annotations --fix`.** Pick `vault check annotations --fix` as canonical because the check is the noun the
  user reaches for and the fix is the action they apply.
  Deprecate `vault sanitize`. The annotations check
  becomes the only path.

### Coordination with adjacent ADRs

The sync-vocabulary ADR's canonical seven-word taxonomy
applies to both surfaces' outputs. The spec-crud-parity
ADR's uniform CRUD shape includes `sync` as part of the
template. Together they constrain `sync` to one
documented shape per noun group.

## Constraints identified

- Deprecating a verb is a user-facing contract change. The
  one-release deprecation window with a warning is the
  standard transition.
- `top-level sync` is a common entry point for pre-commit
  hooks; turning it into a fanout helper keeps it working
  for that use case while reframing its semantic.
- Some users may have memorised `vault sanitize`; the
  deprecation message must point them at the canonical
  replacement (`vault check annotations --fix`).

## Recommendation

For each duplicate-surface pair, pick the canonical form and
deprecate the other. Top-level `sync` becomes a fanout
helper around the granular `spec * sync` verbs. `vault sanitize` is deprecated; `vault check annotations --fix` is
canonical. Full design in the sibling ADR.
