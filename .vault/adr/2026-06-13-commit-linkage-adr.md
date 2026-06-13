---
tags:
  - '#adr'
  - '#commit-linkage'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-commit-linkage-research]]'
---

# `commit-linkage` adr: `opt-in commit-linkage trailer convention` | (**status:** `accepted`)

## Problem Statement

Tooling that correlates git commits to vault records must today do so heuristically - a
commit touching both a vault document and code together, path and time-window overlap,
same-day same-branch co-activity - and grade each correlation by confidence accordingly.
Issue #159 proposes an opt-in convention that lets a commit declare its vaultspec
association explicitly, through a git trailer such as `Vaultspec-Step: W01.P02.S06` or
`Vaultspec-Feature: auth-refactor`, which any such tool can read to resolve a correlation
deterministically instead of guessing. This ADR decides the trailer format core defines
and the tooling core ships to emit and validate it; how any downstream tool consumes the
trailer is outside core's scope.

## Considerations

The grounding research (`2026-06-13-commit-linkage-research`) confirms core has no
commit-message handling, no trailer parsing, and no commit-to-doc correlation today, so
the convention is greenfield. It also fixes the two values a trailer carries: a Step (or
Phase) display path, whose format `display_path.py` already produces
(`S06`, `P02.S06`, `W01.P02.S06`), and a feature tag, validated as kebab-case
(`^[a-z0-9][a-z0-9-]*$`) with an optional leading `#`. Two hook systems exist - the
vaultspec lifecycle engine (events `vault.document.created`, `config.synced`,
`audit.completed`) and the developer `.pre-commit-config.yaml` toolchain run by `prek` -
and only the latter can host a git `commit-msg`-stage hook, which a prior repo ADR
(`2026-03-22-clci-release-adr`) already anticipated. The decisive consideration is the
issue's own hard constraint: the convention must be enrichment, never a prerequisite.

## Constraints

The convention may never become load-bearing. Teams have commit styles core cannot
override, so absence or malformation of a trailer must at most lower a downstream tool's
correlation confidence and nothing more - no commit may be blocked, no vault operation
may fail, and no core command may require a trailer to be present. Any commit-msg hook
core offers must be
advisory: it reports a malformed trailer and exits zero, opt-in by the team explicitly
installing the `commit-msg` stage. Validation must be a pure, offline string operation
over the trailer values reusing the existing identifier and feature-tag formats, with no
git history read required to validate a single message. The trailer format binds future
commits durably, so it must be specified once, in one module, rather than re-derived per
call site. No parent feature is unstable: `display_path.py` and the feature-tag regex are
mature; the only new external touch point is the optional pre-commit hook, which is
inherently opt-in.

## Implementation

Core defines the trailer vocabulary in one place - a `{reference}`-grounded trailer module
beside `display_path.py` and `identifiers.py` - holding the trailer keys
(`Vaultspec-Step`, `Vaultspec-Feature`), the value regexes, and pure
`parse`/`format`/`validate` helpers. Two CLI verbs attach under the existing `vault plan`
group: one emits a well-formed trailer line for a given step or feature (for scripting into
a commit template), and one validates the trailers found in a commit-message file,
reporting malformed values and always exiting zero so it is safe as an advisory hook. The
opt-in automation is a documented `.pre-commit-config.yaml` entry at the `commit-msg`
stage invoking the validate verb against the message file; teams that want it run the
one-time `commit-msg`-stage install, and teams that do not are unaffected. Reading
trailers back out of commit history to act on them is the business of whatever tool
consumes them, never of core: core's responsibility ends at defining the format and
shipping the emit, validate, and optional-hook surface. Exact regexes, verb signatures,
and the hook entry string belong in a `{reference}` document produced at implementation
time.

## Rationale

A git trailer is the right carrier because it is a native, append-only commit-metadata
convention that tools already parse, so adopting teams add it without disrupting their
message style and non-adopters see nothing. Defining the format in a single module mirrors
how `display_path.py` and `identifiers.py` already own their formats and prevents the
drift that an inline-duplicated convention would invite. Routing emit and validate through
`vault plan` keeps the surface where the identifiers it references already live. Choosing
the pre-commit `commit-msg` path over inventing a git event in the lifecycle hook engine
honors both the minimal-machinery principle and the existing precedent, and keeping the
validator exit-zero is the mechanical expression of the enrichment-not-prerequisite
constraint.

## Consequences

Adopting teams give any commit-correlating tool a deterministic, high-confidence signal,
and the format becomes a stable contract such tooling can rely on. The honest costs: core
gains a convention it must version and not break, and the value of the linkage is entirely
proportional to adoption, which core can encourage but never enforce - a low-adoption
repository sees no benefit and that is by design. There is a discipline risk that a future
contributor, seeing the trailer present, treats it as authoritative and lets a code path
depend on it; the codification candidate below exists to forbid exactly that. The path
opens a natural extension - richer trailers (audit ids, ADR stems) under the same module -
without reopening this decision.

## Codification candidates

- **Rule slug:** `commit-trailer-is-enrichment-only`.
  **Rule:** The vaultspec commit-linkage trailer is advisory enrichment; no commit may be
  blocked and no core command may fail or change behavior because a trailer is absent or
  malformed - validation reports and exits zero.
