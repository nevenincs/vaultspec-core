---
tags:
  - '#adr'
  - '#cli-next-step-hints'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-next-step-hints-research]]'
---

# `cli-next-step-hints` adr: `Every command emits an actionable next-step hint` | (**status:** `accepted`)

## Problem Statement

Successful CLI commands terminate without volunteering what to
run next. The pipeline (research, decide, plan, execute, review,
plus the proposed sixth phase codify) is invisible at the verb
boundary; an agent who has just authored a research document
gets no signal that an ADR is the natural follow-on. The single
most useful operational command in the vault subtree
(`vault repair`) is unsurfaced anywhere.

This compounds with the Bridge Gap (round 3a meta-finding):
agents that never see a hint pointing at the spec subtree do
not reach it.

Findings S3 (undiscoverable `vault repair`), round-1 [20]
("no suggestion of what to run next anywhere"), plus the
Bridge Gap structural form.

## Considerations

- The information needed to emit a hint is already available
  at the point of emission. Each verb knows its own output
  state; the framework knows the pipeline's natural follow-
  ons. The cost is the hint mechanism, not the per-verb
  logic.
- Hints must be specific (named command, named arguments) or
  they become noise. A generic "you might want to consider
  the next step" is worse than silence.
- Hints must be conditional on actual state. Suggesting codify
  on an audit with no findings is noise. The verb that knows
  its output knows whether the hint applies.
- Hints must be suppressible. Scripted contexts that parse the
  output cannot tolerate the extra line. A `--no-hints` flag
  or `VAULTSPEC_NO_HINTS=1` environment variable is the
  contract.
- The hint mechanism must coordinate with the
  sync-vocabulary ADR. The seven canonical outcome words
  determine whether a hint should fire (e.g., outcome
  `unchanged` may suggest a different next step than outcome
  `created`).

## Constraints

- Hints are advisory, not authoritative. The verb does not
  refuse to terminate if the user does not run the hinted
  next step. The hint is information; the user decides.
- The hint mechanism does not depend on persistent state. Each
  command computes its own hint from its own output and the
  static pipeline definition. No "agent memory" mechanism is
  introduced.
- Hints must not cite paths that the framework has not
  validated to exist. A hint that proposes a stem that turns
  out to be wrong undermines trust in every subsequent hint.

## Implementation

**Per-verb next-step table.** A static mapping (verb +
outcome → next-verb-suggestion) is defined at the renderer
layer. Examples:

- `vault add research` + outcome `created` →
  `vault add adr --feature <derived> --related <derived-stem>`.
- `vault add adr` + outcome `created` →
  `vault add plan --feature <derived> --related <derived-stem>`.
- `vault add plan` + outcome `created` →
  `vault plan step add <plan-path> ...` (the canonical Step-
  authoring path).
- `vault add exec --all-steps` + outcome `created` (per the
  exec-step-records ADR) →
  `vault plan step check <plan-path> S##` for the next open
  Step.
- `vault add audit` + outcome `created` →
  `vault rule promote --from-audit <stem> --as <rule-name>`
  (per the memory-lifecycle ADR).
- `vault check all` + outcome `unchanged` (clean) →
  `vault repair` (if drift is plausible) or `git commit ...`.
- `vault check all` + outcome `failed` (errors) → the verb
  already emits per-finding fixes; the existing surface
  remains.
- `install` + outcome `created` →
  `vault add research --feature <kebab-tag>` (start the
  pipeline) plus a quickstart pointer to the framework
  manual.
- `vault feature archive` (per the memory-lifecycle ADR's
  fix) + outcome `updated` →
  `vault check all` to confirm the archive completed cleanly
  (this hint is the safety net for the archive verb).

The table is one place. Every verb consults it. Adding a new
verb adds a new entry, not new render logic.

**Conditional emission.** A hint is emitted only when:

- The verb's outcome (per the sync-vocabulary ADR taxonomy)
  has a documented next step.
- The verb's environment has not opted out (`VAULTSPEC_NO_HINTS=1`
  or `--no-hints`).
- The verb's output stream is not JSON. JSON output is
  machine-readable and does not carry prose hints; the next-
  step suggestion is a top-level field instead (`next_step: {command: "...", description: "..."}` alongside the canonical
  `status` field from the sync-vocabulary ADR).

**Discoverable repair.** Surface `vault repair` as a documented
candidate hint from multiple verb endpoints (every `vault check all` with warnings; every `vault sanitize`; every `vault feature index`). The hint mechanism solves the S3 discoverability
finding by construction.

**Top-level help quickstart.** The top-level `vaultspec-core --help` gains a one-line quickstart pointer:

> Run `vaultspec-core install` to set up a new project, then
> `vaultspec-core vault add research --feature <kebab-tag>` to
> start your first feature.

The quickstart is verbatim from the install summary's "first
feature" hint. Two emissions of the same string is intentional;
the user sees it whether they land on `--help` first or
`install` first.

**Companion language updates.**

- Framework manual section on the pipeline is updated to
  describe the sixth (codify) phase and to state that every
  verb in the pipeline volunteers the natural next step in
  its output.
- Builtin rule files that describe the pipeline get a worked
  example showing the hint output and how to act on it.
- Agent personas update to expect a next-step hint at the
  tail of every successful CLI output and to follow it unless
  the operator's instructions override.
- The "next-step hint" pattern becomes a documented framework
  convention; future verbs are expected to register an entry
  in the table at implementation time.

## Rationale

The Bridge Gap meta-finding established that agents do not
reach the spec subtree organically. Adding the codify verb
without making it discoverable would leave the verb existing
but ignored. The discoverability mechanism is what closes the
gap.

Per-command hints are cheaper to implement than command-tree
mining or interactive walkthroughs. The static table is one
file. The renderer integration is one helper. Every verb that
opts in to emit gets the same shape.

The conditional emission keeps the hints honest: an outcome
that has no useful next step emits no hint rather than
inventing one. Suppressibility keeps automation
non-confused.

The mechanism also makes `vault repair` discoverable from at
least four entry points (every `vault check` with warnings,
every `vault sanitize` invocation, every `vault feature index` invocation, and the install summary). The S3 finding
closes automatically.

## Consequences

Gains. The pipeline becomes self-teaching. Fresh-eyes agents
discover the natural follow-on in the output of the previous
command. `vault repair` becomes findable. The Bridge Gap
narrows because every verb whose natural follow-on is in the
spec subtree volunteers the right command.

Difficulties. The static table requires maintenance discipline.
A new verb whose author forgets to register an entry results
in a discoverability regression. The framework's contribution
docs must include "register a next-step entry" as a checklist
item on every new verb.

Pitfalls. Hints that are wrong are worse than no hints. The
hint table must be tested: every entry's command must be
runnable as cited, against the state the emitting verb left
behind. The test surface is small but mandatory.

Pathways. The discoverability mechanism is reusable. Future
work on cross-feature workflows (e.g., "after archiving this
feature, here are the other features whose related links
point into it") can extend the hint table without restructuring
the renderer.
