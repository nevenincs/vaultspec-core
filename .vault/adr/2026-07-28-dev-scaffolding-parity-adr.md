---
tags:
  - '#adr'
  - '#dev-scaffolding-parity'
date: '2026-07-28'
modified: '2026-07-28'
body_schema: 'body-v1'
body_hash: 'sha256:f240d3b4bb106e9158f9be60cbb17c8fef35b5b2a980634f013e938e48569813'
related:
  - '[[2026-07-28-dev-scaffolding-parity-rag-aeat-toolchain-survey-research]]'
---

# `dev-scaffolding-parity` adr: `baseline-ratcheted quality gates` | (**status:** `accepted`)

## Problem Statement

This project's sibling repositories enforce a substantially stricter quality
bar than this one does. Where they gate cognitive complexity, module length,
class shape, cyclomatic complexity, strict typing, dead code, security posture,
and dependency drift, this repository gates style and fast type-checking only.
The gap is not theoretical: the census recorded in
`2026-07-28-dev-scaffolding-parity-rag-aeat-toolchain-survey-research` measures
this tree well outside the range its siblings hold, and none of it was visible
because nothing measured it.

A decision is needed now because adopting the sibling gate set naively fails
closed on day one. Every threshold the siblings run at would reject this
repository immediately, and a gate that cannot be landed green is a gate that
gets disabled.

## Considerations

- The measured distance to the siblings' thresholds is large enough that
  landing at their values is not an option; see the census in
  `2026-07-28-dev-scaffolding-parity-rag-aeat-toolchain-survey-research`.
- A gate whose documented contract and actual exit code disagree is worse than
  no gate, so each dimension must state plainly whether it gates or advises.
- Prior health work under the `health-audit` and `codebase-audit` features
  produced findings but no standing instrument, so regressions after those
  audits were unobservable.
- The siblings' own configuration carries a latent defect this adoption must
  not inherit, recorded in the grounding survey.

## Considered options

- **Adopt the sibling thresholds directly.** Rejected: fails closed on landing
  across every new dimension, which forces either an immediate large refactor
  or disabling the gates.
- **Land every dimension advisory-only and promote later.** Rejected: nothing
  distinguishes a dimension that is genuinely clean from one nobody has looked
  at, and promotion never has a forcing function.
- **Baseline-ratcheted gates.** Chosen: each threshold is calibrated at this
  tree's current worst offender, so the gate is green on landing, blocks any
  regression beyond today's worst, and can only ever be lowered.
- **Skip the dimensions this tree scores badly on.** Rejected: the dimensions
  scoring worst are precisely the ones carrying the most risk.

## Constraints

- Two dimensions cannot run here at all: both read configuration through
  `configparser`, which fails on this repository's pytest log format before
  either inspects a file. The cognitive-complexity dimension covers the
  overlapping signal; the grounding survey records the detail.
- Strict type checking cannot gate at adoption. The volume recorded in the
  survey is annotation debt spread across nearly every module, so it lands
  advisory with the burndown tracked separately.
- The import-convention dimension the sibling enforces does not transfer: this
  package is mixed between absolute and relative intra-package imports, and
  picking a side is an independent decision needing its own record, not a lint
  flag set in passing.
- No parent feature blocks this; the gates are configuration over existing
  tooling.

## Implementation

Every threshold is declared in `pyproject.toml` beside a census comment
recording the distribution it was calibrated from, so a future reader can see
both the number and the distance left to the tool's own default. The
development harness invokes each gate directly rather than reimplementing any
threshold, which is what keeps the harness and the gate from disagreeing.

The dimensions split by consequence rather than by tool. Gating dimensions are
read-only and fail the build. Advisory dimensions report and exit zero, because
each yields a lead to confirm rather than a verdict: reachability analysis
cannot see dynamic dispatch, the security scanner reports this project's
deliberate subprocess design alongside anything real, and dependency drift is a
supply-chain risk rather than a build break. A dimension graduates from
advisory to gating once its finding count reaches zero and can hold there.

A standing aggregate report ranks the worst offenders across every dimension
and always exits zero. It is the measurement instrument the earlier audits
lacked, and it carries a census mode that regenerates the calibration
distributions so a ratchet step is a measurement rather than a guess.

## Rationale

Baseline calibration wins on a knockout criterion the alternatives fail: it is
the only option that is simultaneously green on landing and strictly binding.
Setting each threshold at the current worst offender means the tree passes
today, yet any change that makes any dimension worse than its worst current
case fails immediately. The ratchet direction is enforced by convention rather
than by tooling, which is why every threshold carries its census inline: raising
one is visible in review as a deleted measurement.

The advisory band is not a weaker gate but a different claim. It reports
dimensions whose findings need human confirmation, and stating the exit code
explicitly in the harness prevents the failure mode where a step labelled
report-only silently gates, or a gate never runs because an earlier red step
aborted the job.

## Consequences

The tree gains standing measurement across every dimension its siblings gate,
and regression past today's worst case now fails the build rather than landing
unseen. The aggregate report gives the burndown a target list ordered by
severity instead of a general intention to improve.

Honestly framed, the thresholds this lands at are loose. Several sit far enough
above the tools' defaults that they will not catch a merely bad new function,
only a record-breaking one. The gates are therefore a floor that stops decay,
not a bar that enforces quality, and they only become the latter as the
burndown ratchets them down. That burndown is real work across many sessions,
concentrated in the largest modules, and until it progresses the strict-typing
dimension in particular reports a volume large enough to be easy to ignore.

The ratchet also creates a maintenance obligation: every extraction that pays
down a hotspot should lower the corresponding threshold in the same change, or
the headroom silently reopens for the next regression.
