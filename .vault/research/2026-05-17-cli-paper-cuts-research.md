---
tags:
  - '#research'
  - '#cli-paper-cuts'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-paper-cuts` research: `Smaller paper cuts that share a discipline`

Synthesis note for the residual paper-cut findings — items
that did not warrant standalone ADRs but accumulate into a
felt-quality problem. Captures the evidence behind the sibling
ADR that proposes a discipline pass over the tail.

## Findings

### Unhydrated-placeholder warnings on every fresh scaffold

Round 1 [06], round 2 confirmations, round 3 confirmations.
Every `vault add adr`, `vault add plan`, `vault add exec`
invocation emits warnings about `{adr}`, `{research}`,
`{reference}` tokens that appear inside HTML guidance
comments meant for the human author. The warnings fire
unconditionally on a brand-new scaffold. Both agents learned
to ignore them within their first round.

The fix is the scaffolder-integrity ADR's invariant plus a
narrowed placeholder check: tokens inside `<!-- ... -->`
regions are not unhydrated frontmatter; they are intentional
template guidance.

### `--dev` flag pollutes every consumer's `--help`

Round 1 [03]. The `--dev` flag exists so framework maintainers
can run the CLI against the source repository itself
(activating a guard). It is rendered on `install`, `uninstall`,
`sync`, `migrations run`, and possibly more. Its help text
describes a "source-repo guard" the framework's consumers do
not have, do not need, and do not understand.

The fix is to mark `--dev` as a hidden flag in the CLI
framework (`hidden=True`) and document developer mode in a
contributor doc.

### `vault graph --help` lies about its usage line

Round 1 [18]. The Click/Typer wiring renders `Usage:
vaultspec-core vault graph [OPTIONS] COMMAND [ARGS]...`
despite the verb being a leaf with no subcommands. New readers
hunt for subcommands that do not exist.

The fix is in the framework integration: leaf commands must
render `[OPTIONS]` only, not `COMMAND [ARGS]...`.

### `vault feature list` text trails an unexplained `plan` token

Round 3b S20. Text output trails each feature with an
unattached `plan` token: `snippets  9 docs  (adr, audit,
index, plan, research) plan`. The `--json` form has
`has_plan: true` instead.

The fix is to remove the trailing token from text output (the
`has_plan` semantic is already in the parenthesised list).

### `migrations status` reports a fishy applied entry

Round 3a [57]. The output names `applied 0.1.17
index_subfolder` even on a single-registered-migration
workspace. Joan flagged it as suspicious. Xavi round 3
([32]) saw the same line.

The fix needs investigation: is the report correct (the
migration was applied at 0.1.17 and is still recorded
provenance) or wrong (the report draws from a stale
registry)? Either way, the wording should be unambiguous
about whether this is provenance or a current report.

### `spec hooks list` truncates the event-name column

Round 3a [54]. The `list` output truncates the event-name
column, but `spec hooks run` requires the untruncated name.
Output column truncation breaks the input contract.

The fix is to not truncate columns whose values are consumed
by sister commands. Either widen the column (terminal width
permitting) or render the full name on its own line.

### `spec system show` describes a sync target that does not exist

Round 3a [53]. The verb references a sync target the
workspace Joan tested against does not have. The verb is
wired before the destination is. Either the verb should
detect the missing destination and report it explicitly, or
the verb should be unwired until the destination ships.

### Outcome line shape varies within the same group

Round 3a [58]. `spec rules` emits both "Rule source updated"
and "Reverted rule" as outcome strings. Subject-first
vs. verb-first. The sync-vocabulary ADR's canonical seven-
word taxonomy fixes the high-level inconsistency; this
ancillary inconsistency disappears when every verb routes
through the same renderer.

### `vault check all` + `spec doctor` leaves the operator guessing

Round 3a S17. Two clean exit codes still does not answer "am
I safe to commit?". Joan called this out: no single "is the
workspace green?" entry point.

The next-step-hints ADR's pattern partially addresses this
(clean `vault check all` hints at `git commit` or `vault
repair`). A small additional fix is useful: a top-level
`vaultspec-core doctor` that calls both `vault check all`
and `spec doctor` and reports a unified pass/fail with one
exit code.

## The discipline that ties these together

Each item above is small. Together they form the felt
roughness an experienced operator describes as "feels like
the CLI was built by accretion". The discipline shared
across them is: every output is intentional, every flag is
intentional, every help-text line is intentional, every
column width is intentional.

A one-time sweep is the right shape rather than per-finding
ADRs. The sibling ADR proposes the sweep as a single piece
of work with a checklist deliverable.

## Recommendation

Run a single sweep pass over the CLI's output, help text,
column rendering, and hidden-flag policy. Treat the sweep as
a documented discipline rather than a set of bug fixes. Add
a small contribution check ("when adding a new verb, audit
its output against the discipline"). Full design in the
sibling ADR.
