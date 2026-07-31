---
tags:
  - '#adr'
  - '#guard-subject-integrity'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:a17bc68ed7f5fe1e9d35d4dccf5706dcef4520fdedd027db4e827ceadf82b52f'
related:
  - '[[2026-07-30-guard-subject-integrity-research]]'
  - '[[2026-05-15-operator-cli-sync-authority-adr]]'
  - '[[2026-05-15-template-annotation-sanitization-adr]]'
---

# `guard-subject-integrity` adr: `repository guards validate sources, not generated mirrors` | (**status:** `proposed`)

## Problem Statement

The template-annotation guard resolves its subject as the installed
`.vaultspec/templates/*.md` mirror (`dev/guards/test_template_annotations.py:22`) - the
tree the sync pipeline renders from `src/vaultspec_core/builtins/templates/` - and never
reads the source tree itself. The package docstring declares the installed mirror as an
intended subject (`dev/guards/__init__.py:9`), so the targeting is documented policy, not
an accident.

`2026-07-30-guard-subject-integrity-research` records both the survey behind this record
and the failure mode observed in practice: the guard stayed green while a new template
field was added to the source and committed, and turned red only when the mirror was later
regenerated - not because anything broke, but because it finally saw a field the source had
carried for some time. The guard lags reality by exactly one sync, so it passes at the
moment of the change and fails at the moment of unrelated hygiene, for an unbounded
interval. The immediate symptom was patched by admitting the new field to the allowed-keys
set; the subject question is what this record decides.

## Considerations

- The research's survey found exactly one guard validating a generated artefact - the
  template-annotation module above - against an in-package counter-example already globbing
  the source (`dev/guards/test_cli_language_contract.py:35`). This is a one-module defect,
  not a harness-wide pattern, which is what makes a proportionate remedy available.
- The one adjacent instance the survey found sits outside the guard package and is a
  dev-only measurement input rather than a gate; it is left outside this decision.
- Mirror parity already has an owner. The sync surface renders the mirror and the doctor
  diagnoses divergence (`2026-05-15-operator-cli-sync-authority-adr`); the project forbids
  hand-editing the mirror. A guard asserting on the mirror therefore re-tests a derivative
  whose freshness a different, authoritative surface owns.
- Precedent for source-primacy: `2026-07-23-vault-check-validators-adr` ratified deriving
  section contracts from the shipped templates as single source of truth, precisely so
  contract and source can never drift.
- The content rules the guard enforces (no frontmatter comment directives, no malformed
  HTML comment syntax, a closed frontmatter key set) descend from
  `2026-05-15-template-annotation-sanitization-adr` and are not in question - only which
  tree they are enforced against.

## Considered options

- **Repoint the guard to the builtins source tree (chosen).** The guard fails in the same
  commit that introduces a violation, with zero dependence on sync freshness.
- **Dual-subject: glob both source and mirror.** Rejected: the mirror half re-tests what
  sync and doctor own, and converts the one-sync lag into red noise timed to regeneration
  commits - the inverted signal just observed, kept on purpose.
- **Add a dedicated source-versus-mirror parity guard.** Rejected: a second parity
  implementation beside the doctor's canonical sync comparison; parallel implementations of
  the same contract drift, and drift in a parity checker is maximally confusing.
- **Status quo plus regeneration discipline.** Rejected: that discipline is the thing that
  observably failed, and a guard whose correctness depends on an unenforced habit is not a
  guard.

## Constraints

- The change is a one-line subject repoint plus docstring corrections in the guard module
  and the package docstring; no new dependencies, no fixture changes.
- The three content rules and the allowed-keys set are unchanged by this record.
- Whether template-mirror staleness should itself gate commits is the doctor's contract and
  explicitly out of scope; this record removes the guard's dependence on that contract
  rather than tightening it.

## Implementation

The template-path resolver in the guard module resolves the builtins templates tree rather
than the installed mirror. The module docstring and the package docstring are corrected to
state the policy this record adopts for the harness: repository guards validate the source
of truth; generated artefacts - the installed mirror, provider stubs, rendered outputs -
are validated only by the machinery that generates and diagnoses them. The policy binds
future guards; the survey above is the evidence that no other existing guard needs to move.

## Rationale

The knockout criterion is temporal: a guard exists to fail on the commit that introduces
the defect, and a derived subject makes that impossible by construction - the derivative
changes one sync later, so the guard is green at the moment of the defect and red at the
moment of hygiene. The observed incident is a clean instance of both halves of the
inversion. Repointing restores cause-aligned failure at the cost of nothing: the mirror's
own correctness is not orphaned, because parity with the source is precisely what the
sync-authority surface exists to own. Scoping the decision to a policy sentence plus a
one-line repoint, rather than any broader restructuring, is proportionate to a survey that
found a single offender against an in-package counter-example already doing it right.

## Consequences

- Template-shape violations fail in the commit that causes them; a stale mirror can no
  longer mask a source defect or fabricate a failure on regeneration.
- The guard no longer exercises the installed mirror at all. That is correct ownership, but
  it means a sync pipeline defect corrupting the mirror is visible only to the doctor -
  accepted, and no worse than today, since the incident shows the mirror-facing guard also
  fails to catch staleness (it goes green on it).
- The package docstring stops mis-describing the harness's subject, and future guard reviews
  inherit a one-line test: is the subject a source?
- The statistics package's mirror read remains as-is; if its lag ever misleads an analysis,
  it becomes its own small decision rather than a silent inheritance of this one.
