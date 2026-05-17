---
tags:
  - '#adr'
  - '#cli-exec-step-records'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
  - "[[2026-05-17-cli-exec-step-records-research]]"
---

# `cli-exec-step-records` adr: `Make vault add exec produce per-Step records the framework rules require` | (**status:** `accepted`)

## Problem Statement

The framework's own rules require per-Step execution records under
`.vault/exec/{date-feature}/{date-feature}-S##.md` with populated
`step_id` frontmatter. The only CLI path for authoring exec
records (`vault add exec`) cannot produce that layout. It accepts
no `--step` flag, emits a single flat document per feature
instead of one per Step, and writes `step_id: '{S##}'` as a
literal placeholder.

The rules describe the artifact; the CLI cannot produce it. An
agent following the rules strictly hits a wall on phase four of
the canonical five-phase pipeline.

Finding B1 in the audit; reproduced by Xavi round 1 and Joan
round 2.

## Considerations

- The disagreement is between rules and scaffolder. Two
  resolutions: change the rules to fold all Steps into one exec
  document (rejected — see research note), or teach the
  scaffolder Step-awareness. Step-awareness is the right call.
- The CLI already has a plan parser. It can read the plan
  pointed at by `--related`, enumerate Steps, derive identity,
  derive scope, populate path and frontmatter automatically.
- A 30-Step plan produces 30 Step Records. Individual-step
  authoring is the unit; a bulk form for all-Steps-at-once is a
  necessary ergonomic helper.
- The same scaffolder-integrity invariant from the sibling
  scaffolder-integrity ADR applies: the new path must not emit
  any value its validator would reject.

## Constraints

- `vault add exec`'s current signature (`--feature`, `--title`,
  `--date`, `--related`, `--dry-run`, `--json`, `--target`) is a
  user contract. The change adds `--step` as a new required
  flag where Step Records are intended (with a fall-through that
  preserves the legacy flat-document path for one release
  cycle, then removes it).
- The path computation must use the same date/feature convention
  the rest of the framework uses, and survive the supersession
  in the memory-lifecycle ADR (an ADR's `--date` is the date
  the document was authored; an exec record's date is the date
  the Step was implemented; these may differ on long-running
  plans).
- Step Records are user-edited after scaffolding; the
  scaffolder must produce a clean editable surface, not an
  over-populated wall.

## Implementation

**Required `--step` flag.**

- `vault add exec --feature <tag> --step S<NN> --related
  <plan-stem>` becomes the canonical invocation.
- The CLI reads the plan referenced by `--related`, looks up
  the named Step, populates the output:
    - Path: `.vault/exec/{date}-{feature}/{date}-{feature}-S##.md`
      (creating the per-feature directory on first call).
    - Frontmatter: `step_id: 'S##'`, `related: ['<plan-stem>']`,
      `tags: ['#exec', '#<feature>']`, `date: <today>`.
    - Body: heading from the Step's `action`; pre-populated
      "Scope" section listing the Step's `scope` paths; empty
      "Outcome" and "Notes" sections for the author to fill.
- `--title` becomes optional; when supplied it overrides the
  derived heading. When omitted, the Step's `action` is used
  verbatim.

**Bulk `--all-steps` form.**

- `vault add exec --feature <tag> --related <plan-stem>
  --all-steps` enumerates every Step in the plan and scaffolds
  one exec record per Step, returning a list of created paths.
- `--all-steps` is mutually exclusive with `--step`.
- Idempotent: re-running against an already-scaffolded plan
  skips Steps whose exec record already exists, with the
  canonical outcome `skipped` (per the sync-vocabulary ADR).
  Use `--force` to overwrite (and adopt the same `--force`
  semantics defined by the sync-vocabulary ADR — overwrite
  existing, do not prune).

**Removal of placeholders.**

- The literal `step_id: '{S##}'` is removed from the template;
  it is computed from `--step` or `--all-steps` enumeration.
- The literal `<display-path>` is removed; the body lists the
  Step's `scope` paths in a `Scope` section.
- Subject to the scaffolder-integrity invariant: the writer
  validates its output before flushing.

**Companion language updates.**

- The framework rule files that describe Step Records get
  updated to reference the new CLI invocation as the canonical
  authoring path. The "do not hand-edit" rule remains; the new
  CLI path is what makes that rule honestly followable.
- The plan template's guidance section gets a one-line pointer
  to `vault add exec --step` as the natural follow-on once a
  Step is implemented.
- Agent personas get the same pointer in their post-step
  reasoning template: "when you finish a Step, scaffold its
  exec record via `vault add exec --step`".
- `vault plan status` output gains a one-line hint when a Step
  is completed but has no exec record yet, pointing the user
  at the right command.

## Rationale

Two independent agents on two different feature implementations
hit this wall and chose to skip exec records rather than violate
the framework's own no-hand-edit rule. The CLI is the
bottleneck; the rules are the right artefact shape.

Step-aware scaffolding reuses machinery the CLI already has
(plan parser, frontmatter helpers, path conventions). The
implementation cost is small relative to the structural
benefit: the pipeline's fourth phase becomes authorable for
the first time.

The bulk `--all-steps` form is essential because the unit cost
of one-call-per-Step on a real 20-Step plan dominates the
mental cost of remembering the command. The bulk form is
idempotent so an agent can run it any time without thinking
about state.

## Consequences

Gains. The execute phase of the pipeline gains a CLI-correct
authoring path for the first time. The framework's rules and
the framework's scaffolder agree. The literal `step_id: '{S##}'`
placeholder is gone; the literal `<display-path>` is gone; the
scaffolder-integrity invariant covers exec records the same way
it covers plans.

Difficulties. The legacy flat-document path needs a deprecation
window. Existing exec records authored under the old shape have
to either remain valid (the rule about per-Step records becomes
"per-Step, OR one legacy flat doc per feature") or be migrated.
The conservative choice is to keep the legacy shape valid for
historical documents while requiring the new shape for new
ones.

Pitfalls. The `--all-steps` form is destructive against existing
exec records when run with `--force`. The default behaviour
(skip existing) is the safe one; the `--force` mode must be
named, gated, and announced.

Pathways. Once Step Records are CLI-authorable, the audit-of-
implementation feedback loop closes: a reader can read the
plan, read each Step's exec record, and see the implementation
trail at Step granularity. The "is this feature really done"
question stops requiring code inspection.
