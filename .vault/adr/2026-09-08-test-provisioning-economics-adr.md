---
tags:
  - '#adr'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:769bec4a8793dd4c4cc3424ce0e43bbb99ab2e2134e35f5e3beca63c5a237b94'
related:
  - "[[2026-09-08-test-provisioning-economics-broad-lane-profile-research]]"
  - "[[2026-09-08-test-provisioning-economics-suite-defects-audit]]"
---

# `test-provisioning-economics` adr: `The test harness may skip work the test cannot observe` | (**status:** `accepted`)

## Problem Statement

The `broad` lane takes 36 minutes on Linux and 46 on Windows, and neither number
is explained by the tests. Fixture setup accounts for 6h46m42s of measured work
against a test-body total that is a small fraction of it, and one function-scoped
fixture, `synthetic_project`, is 59% of that alone: it rebuilds a byte-identical
245-file install 391 times. 61% of each rebuild is `os.fsync`, called once per
file by `atomic_write_bytes`.

Both costs are real work that the tests requesting them cannot observe. No test
asserts power-loss durability, and no test asserts that its workspace was
provisioned in-process rather than copied. But whether the harness is allowed to
skip such work is not a question the existing corpus answers. Ten ADRs name
`atomic_write` or `atomic_write_bytes` as the shared write path; none states what
it guarantees, so there is no recorded contract to diverge from, and any
divergence introduced without one becomes an undocumented difference between what
CI proves and what ships.

The decision is needed before the work rather than after, because the alternative
is a harness that quietly tests something other than the product.

## Considerations

- The atomicity of `atomic_write_bytes` does not depend on `fsync`. It comes from
  `O_EXCL` temp creation (`src/vaultspec_core/core/helpers.py:505`) and
  `os.replace` (`:587`). The `fsync` at `:681` buys durability across power loss
  and nothing else. Suppressing it changes no observable ordering within a
  process.
- The suite already states that this property is untested, at
  `src/vaultspec_core/core/tests/test_manifest_exclusive_atomicity.py:14`. This
  is a boundary the repository has already drawn implicitly; the decision is
  whether to draw it explicitly.
- `fsync` serialises at the device, so its cost is a function of every other
  writer on the volume rather than of this suite. Measured spread on one machine
  was 15.9s to 72.0s for the same install. That is why the cost cannot be
  engineered away by adding workers, and why parallelism has to come second.
- The self-hosted Windows runner is a shared workstation carrying 23-25
  concurrent runner processes during measurement, so the Windows lane competes
  for exactly the resource `fsync` serialises on.
- Parallel execution is not merely an optimisation here: it exposed two isolation
  defects and four tests that terminate their own runner
  (`2026-09-08-test-provisioning-economics-suite-defects-audit`). Adopting it
  changes what the suite is capable of detecting.
- The corpus is deterministic by construction: `build_synthetic_vault` is seeded,
  and the install that follows is a pure function of the bundled builtins and
  that corpus. Reuse is safe because of that, not in spite of it.

## Considered options

- **A stated test-harness boundary: the harness may skip work whose effect no
  test can observe, and must skip nothing else (chosen).** Names the principle
  rather than the two instances, so the next such question has an answer.
  Instantiated here as fsync suppression and template reuse. Costs: the harness
  and production now differ in a way a reader must be told about, and the
  boundary needs policing or it will widen.
- **Leave the write path alone; buy faster hardware or accept the runtime
  (rejected).** Honest, and preserves an exact production-to-test match. Rejected
  because the match is already inexact - the property is untested either way -
  and because a 46-minute lane changes behaviour: it is the reason parallelism
  was never adopted, and therefore the reason two isolation defects survived.
- **Suppress fsync globally, including production (rejected).** Simplest, and
  removes the divergence entirely. Rejected outright: durability across power
  loss is the reason the call is there, and this repository writes a user's
  managed files. The cost is paid where it buys something.
- **Make durability configurable at runtime (rejected).** A settings flag would
  let operators trade durability for speed. Rejected as scope this work has no
  evidence for: no operator has asked, and a knob on a correctness property is a
  liability that outlives the performance problem that suggested it.
- **Session-scoped shared workspace, no per-test copy (rejected).** Cheaper still
  than cloning. Rejected because the tests mutate their workspace; sharing one
  would couple every test to every other and trade a runtime problem for an
  isolation problem, which is the defect class this same audit reports.

## Constraints

- Production behaviour must not change. The boundary is the test harness, and it
  must be established somewhere a production code path cannot reach.
- Per-test isolation must survive. Each test keeps its own writable tree; reuse
  applies to the construction of that tree, not to the tree itself.
- The suppression must be observable. A reader of a test run must be able to tell
  the harness is operating under this boundary rather than discover it in a
  conftest months later.
- The two isolation defects and the four self-terminating tests are prerequisites
  for parallelism, not consequences of it. They are fixed as defects on their own
  terms, not pinned or grouped to make a runner happy.
- Measurements were taken on a machine concurrently running this repository's CI,
  so targets are stated as ratios against a re-measured baseline rather than as
  absolute seconds.

## Implementation

The boundary is stated once, in the repository-root `conftest.py`, and applies to
every invocation however a lane reaches pytest - the same placement and the same
reasoning as the CI-report hook already there.

`os.fsync` is replaced with a no-op for the duration of a test session and
restored at the end. Production code is untouched: `atomic_write_bytes` keeps its
call, and an installed `vaultspec-core` fsyncs exactly as it does today.

The identical-tree fixtures build their workspace once per session and clone it
per test. `synthetic_project`, `synthetic_project_manifest`, and the `vault_root`
family become session-scoped template builders plus a function-scoped copy. Each
test still receives its own writable directory.

Parallel execution is enabled on the lanes only after the audit's isolation
defects are fixed. The watchdog cohort, which terminates its own ancestor by
design, is kept on a single worker by an explicit group rather than by luck.

A guard asserts the boundary holds: that production code carries no test-aware
branch, and that the fsync suppression is confined to the harness.

## Rationale

The principle chosen is narrower than "make tests fast" and wider than "skip
fsync". What licenses both changes is the same property: the work being skipped
has no effect any test can detect. That is checkable, which a vaguer efficiency
mandate would not be, and it draws a line the next optimisation can be held
against - a fixture that skipped work a test could observe would be out of bounds
under this decision even if it were faster.

`fsync` is the right thing to suppress rather than the fixtures alone because it
is the half that does not scale. Cloning templates would cut the work; only
removing the device serialisation makes the remaining work parallelisable, and
the measurements show parallelism alone moving the setup median in the wrong
direction.

Production is left alone because the guarantee is worth its cost where a real
user's files are at stake, and because the divergence is only defensible while it
is confined to a context where the guarantee is provably unobservable.

The isolation defects are treated as prerequisites rather than fallout because
they are true today: the tests are wrong now and the single-process lane is
hiding it. Fixing them under this decision is the honest sequence; grouping them
away to make a parallel run green would spend the audit's finding to buy a
number.

## Consequences

The suite stops paying for a guarantee it never checked, and the lane becomes
parallelisable rather than merely parallel. The measured ratios put the fixture
cost within reach of a small multiple of a `copytree`, which is the floor for
this fixture shape.

The honest cost is a stated difference between the harness and production. A test
run no longer exercises the fsync path, so a regression that broke only fsync
ordering would not be caught by this suite. It was not caught before either, but
that was an accident and this is a decision, which makes it this record's
responsibility to say so.

The boundary will be under pressure to widen. Every future slow fixture will
present itself as work no test can observe, and some of those claims will be
wrong in ways that are hard to see. The guard is what keeps the principle from
degrading into a habit, and it is load-bearing rather than decorative.

Enabling parallel execution also changes what the suite detects. Tests that pass
today because they run alone will fail, and that is the decision working rather
than the decision breaking. The first such failures are already named in the
audit; more should be expected.
