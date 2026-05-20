---
tags:
  - '#research'
  - '#cli-exec-step-records'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-exec-step-records` research: `vault add exec cannot produce conformant Step Records`

Synthesis note for finding B1 — the framework's own rules require
per-Step execution records, and the CLI cannot author them.

## Findings

### The rules require Step Records the CLI cannot author

The framework rules (loaded by `vaultspec-core install` into the
project's agent context) describe per-Step execution records
located at `.vault/exec/{date}-{feature}/{date}-{feature}-S##.md`,
each carrying a populated `step_id` frontmatter field tying it
back to a specific Step in a specific plan.

`vault add exec` is the only CLI path for authoring execution
records. It accepts `--feature`, `--title`, `--date`, `--related`
— but no `--step`, `--phase`, or `--wave` flag. It produces a
single flat document at `.vault/exec/{date}-{feature}-exec.md`,
not the per-Step folder layout. The frontmatter contains the
literal string `step_id: '{S##}'` (the same scaffolder antipattern
flagged in finding B2/B5).

### Reproductions

Xavi hit this in round 1 ([10] in his SESSION.md), correctly mapped
"execute the plan" to `vault add exec`, walked into the wall, and
chose to skip exec records entirely rather than hand-author files
in violation of the framework's no-hand-edit rule.

Joan hit the same wall in round 2 ([33], [34]). His commands log
shows `vault add exec ...` returning exit 0 with the same
non-conformant output. He logged it as a wall and moved on.

Two independent reproductions across the audit. The bug is real,
persistent, and structurally on the critical path of the pipeline:
"execute the plan" is the fourth of five canonical phases.

### What the rules require vs. what the CLI produces

The rules require:

- Per-Step file: one document per Step in the plan, at
  `.vault/exec/{date-feature}/{date-feature}-S##.md`.
- `step_id` frontmatter referencing the Step's canonical
  identifier.
- Body sections aligned with the Step's action, scope, and
  outcome.
- A `--related` pointer back to the plan.

The CLI produces:

- One flat document at `.vault/exec/{date-feature}-exec.md`.
- `step_id: '{S##}'` literal frontmatter.
- A heading containing both the title and a `<display-path>`
  placeholder.
- `--title` substituted into the body, not the path.

The disagreement is total. Either the rules need to change to
match what `vault add exec` produces (one exec record per
feature, not per Step), or `vault add exec` needs to learn
Step-awareness.

### Why the rules are probably correct, not the CLI

Per-Step execution records are useful work product. Each Step
has its own action, its own scope, its own success criteria; an
exec record per Step lets a reader trace the implementation of
each Step individually. Folding all Steps into one document
loses the granularity the plan's Step IDs were introduced to
provide.

The plan-status verb (`vault plan status`) already reports per-
Step completion. Per-Step exec records let that report cross-
reference into a real artifact. Without per-Step records, the
completion percentage is the only signal a Step has been
implemented.

### Adjacent paper cut — the literal `<display-path>` token

The scaffolder emits the string `<display-path>` into the
generated body. The user is expected to know what value to
substitute. The token is intended to be replaced by the actual
file path the step touched. The CLI knows that path from the
Step's `scope` field but does not substitute it.

## Constraints identified

- Per-Step records compound with the per-feature record count.
  A 30-Step plan produces 30 exec records. The CLI must handle
  the iteration ergonomically (single command per Step, plus a
  bulk `vault add exec --all-steps` form).
- `step_id` is canonical and stable; the path can derive from
  it. The CLI has the parser to read the plan; reusing it for
  exec authoring is cheap.
- `--related` should default to the plan document when authoring
  an exec record. The user should not have to repeat the plan
  stem on every Step.

## Recommendation

Make `vault add exec` Step-aware: required `--step` flag, derived
output path, populated `step_id`, derived `display-path` from
Step's `scope`, default `--related` to the parent plan. Add a
`vault add exec --all-steps` bulk form for scaffolding all
Step Records of a plan in one call. Full design in the sibling
ADR.
