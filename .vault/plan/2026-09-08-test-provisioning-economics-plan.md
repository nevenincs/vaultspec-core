---
tags:
  - '#plan'
  - '#test-provisioning-economics'
date: '2026-09-08'
tier: L2
related:
  - '[[2026-09-08-test-provisioning-economics-adr]]'
modified: '2026-09-09'
body_schema: body-v2
body_hash: 'sha256:6822b9b9d4ad5cedea42a2fddce2137afb4bd9cc4e02cfa348d9cf4c743752fa'
---

# `test-provisioning-economics` plan

## Description

Approved 2026-09-08

Authorization basis: the user directed this work in-session - file the headline
findings, persist them, write the required ADR and plan, and execute all fixes -
and granted explicit advance authorization to proceed without further approval,
with the stated goal of matching the measured headline numbers rather than
changing code for its own sake.

The `broad` lane costs 36 minutes on Linux and 46 on Windows, and the tests are
not why. Fixture setup is 6h46m42s of measured work against a test-body total
that is a small fraction of it; `synthetic_project` alone is 59% of that,
rebuilding a byte-identical 245-file install 391 times, and 61% of each rebuild
is `os.fsync`. The measurements are in
`2026-09-08-test-provisioning-economics-broad-lane-profile-research`; the defects
found alongside them are in
`2026-09-08-test-provisioning-economics-suite-defects-audit`.

Decision coverage: `2026-09-08-test-provisioning-economics-adr` governs every
Phase here and is accepted. It settles the one commitment this work depends on -
that the harness may skip work whose effect no test can observe, and nothing else

- and bounds the two instances P01 and P02 implement. No other accepted ADR
  governs the write path's durability contract; ten name `atomic_write` without
  stating what it guarantees, which is the gap that ADR fills. `2026-03-23-test-quality-adr`
  is `accepted` but is an unfilled template and settles nothing, so it was assessed
  and set aside rather than relied on.

The Phases are ordered by dependency, not by size. P01 comes first because
`fsync` serialises at the device: until it is gone, cloning templates cuts work
that parallelism would then re-queue, and the measurements show workers making
setup medians worse rather than better. P03 precedes P04 because the isolation
failures are true today and the single-process lane is hiding them; fixing them
is the honest prerequisite for a runner, not fallout from one.

Out of scope, and recorded in the audit rather than actioned here: the two failing
`test_discovery_guidance` guards, the empty `2026-03-23-test-quality-adr`, and the
drift between `2026-09-05-provisioning-tests-adr` and the self-hosted Windows leg
the workflow now uses.

## Steps

### Phase `P01` - establish the durability boundary

Move the fsync cost out of the harness and prove production is untouched.

- [x] `P01.S01` - Suppress os.fsync for the duration of a test session in the repository-root conftest, restoring it on unconfigure; `conftest.py`.
- [x] `P01.S02` - Guard that the boundary is confined to the harness: no test-aware branch in production code, one fsync call site; `dev/guards`.
- [x] `P01.S03` - Re-measure the install cost under the boundary and record the ratio against the pre-change baseline; `dev/guards`.

### Phase `P02` - reuse the provisioned workspace

Build each identical workspace once per session and clone it per test.

- [x] `P02.S04` - Rebuild synthetic_project and synthetic_project_manifest as a session template plus a per-test clone; `src/vaultspec_core/tests/cli/conftest.py`.
- [x] `P02.S05` - Rebuild the mcp_server vault_root fixtures on the same session-template-plus-clone shape; `src/vaultspec_core/mcp_server/tests/conftest.py`.
- [x] `P02.S06` - Convert the remaining per-test installs: fresh_clone, executor workspace, preflight installed_workspace; `src/vaultspec_core/tests`.

### Phase `P03` - fix the defects parallelism exposed

Repair the isolation failures and contain the self-terminating cohort, on their own terms.

- [x] `P03.S07` - Establish why four xdist workers died, treating the cause as unknown and excluding resource exhaustion first; `src/vaultspec_core/mcp_server/tests/test_watchdog.py`.
- [x] `P03.S08` - Re-measure the parallel run on an uncontended machine, so the crash evidence is not confounded by the CI runner; `dev/toolchain.py`.
- [x] `P03.S09` - Contain or fix whatever S07 identifies, on the evidence rather than on the retracted watchdog theory; `src/vaultspec_core/mcp_server/tests/test_watchdog.py`.

### Phase `P04` - turn on parallel execution

Wire the runner into the lanes and CI now that the suite can survive it.

- [x] `P04.S10` - Give the broad, harness and repo lanes a worker count in the harness registry; `dev/toolchain.py`.
- [x] `P04.S11` - Re-measure the full lane under the boundary and the runner, and record it against the headline numbers; `dev/toolchain.py`.

### Phase `P05` - close the timing blind spots

Time the phase that consumes the time, and derive the sleep windows from what they measure.

- [x] `P05.S12` - Time fixture setup as well as the call phase, so a hung fixture names itself; `pyproject.toml`.
- [x] `P05.S13` - Derive the watchdog sleep windows from the poll interval they measure; `src/vaultspec_core/mcp_server/tests/test_watchdog.py`.

## Parallelization

Phases carry hard ordering and run in sequence. P01 must land before P02, because
cloning a template that is still being written through 426 fsyncs measures the
device rather than the change. P03 must land before P04, because turning on a
runner over known isolation failures would report them as flakes. P05 is
independent of P02 through P04 and could run at any point after P01; it is placed
last only so the timing changes do not perturb the measurements P01.S03 and
P04.S11 record.

Steps within a Phase are independent and may be executed in any order, with two
exceptions: P01.S03 measures what P01.S01 establishes, and P04.S11 measures what
P04.S10 enables.

No Step is assigned to a parallel worker. The Phases are small, several touch the
same two conftest files, and the plan's own subject is a suite that has just been
shown to fail when concurrent writers share a tree.

## Verification

- `just test-broad` passes, with no test newly skipped, xfailed, or deselected
  relative to the pre-change collection count of 4410.
- The full lane completes in under 10 minutes on the Linux leg, measured against
  a re-measured baseline on the same machine rather than against the 36-minute
  historical figure, since the profiling machine was concurrently running CI.
- `install_run(provider="all")` under the harness boundary costs within a small
  multiple of a `copytree` of the same tree, matching the measured 13x and 19x
  ratios in the research record.
- A guard fails if production code acquires a test-aware branch, or if `os.fsync`
  gains a second call site outside the harness.
- The two isolation failures named in the audit pass under parallel execution,
  and pass for the reason stated in each fix rather than by being grouped onto
  one worker.
- No xdist worker is reported down during a full parallel run.
- A fixture that hangs is reported by name, verified by inducing one.
- Production `install`, `sync`, and `uninstall` behaviour is unchanged: the
  provisioning tests that drive real environments pass unmodified.
