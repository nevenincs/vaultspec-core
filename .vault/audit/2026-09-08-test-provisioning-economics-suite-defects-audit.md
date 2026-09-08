---
tags:
  - '#audit'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:ef97d5e83ca80c2460f78077827225daeb9e1eae3aec7fabbf3e439fb859e805'
related:
  - '[[2026-09-08-test-provisioning-economics-broad-lane-profile-research]]'
---

# `test-provisioning-economics` audit: `Defects surfaced while profiling the broad lane`

## Scope

The `broad` test lane on `main` at `b5c7f256`, profiled on 2026-09-08 to find why
it takes 36 minutes on Linux and 46 on Windows. Audited: fixture provisioning,
the shared write path the fixtures drive, the timeout configuration, and the
behaviour of the lane under parallel execution.

The measurements are not repeated here; they live in
`2026-09-08-test-provisioning-economics-broad-lane-profile-research`. This record
holds only the defects profiling exposed, several of which are independent of the
performance work and would have stayed hidden without it.

## Findings

### test-isolation | high | Two tests pass serially and fail under parallel execution

Running the lane at `-n 12` produced two failures that do not reproduce
single-process:
`src/vaultspec_core/tests/cli/test_collectors.py::TestModeMismatchPerPackage::test_companion_package_without_own_artifacts_is_clean`
and
`src/vaultspec_core/tests/cli/test_doctor.py::TestDoctorCommand::test_json_exit_code_reflects_corrupted_state`.
Both were re-run serially and passed. These are latent isolation defects the
single-process lane has been concealing; they are evidence about the tests, not
about the runner.

### watchdog-self-termination | high | Watchdog tests kill their own test-runner worker

Four workers were lost during the parallel run, each reported as
`node down: Not properly terminated` (gw1, gw4, gw8, gw11).
`src/vaultspec_core/mcp_server/tests/test_watchdog.py` exercises ancestor-death
reaping: the code under test walks up the process tree and terminates an
ancestor. Under a parallel runner that ancestor is the worker process, so the
test kills the harness executing it. This is a real property of the tests,
visible only under parallelism, and it bounds how the suite can be parallelised.

### failing-guards-on-main | high | Two repository guards fail on a clean checkout

`src/vaultspec_core/tests/test_discovery_guidance.py::TestRegistryIsGrounded::test_home_defines_every_canonical_sentence`
fails single-process on `main` at `b5c7f256`, unrelated to parallelism or to any
change made here. `TestSequenceHasOneHome::test_every_rag_mentioning_entry_point_states_the_fallback`
in the same file also failed in the full run. These are repository-content
guards, so the failure means the guarded content and the guard disagree today.

### untimed-setup-phase | medium | The timeout does not cover the phase that consumes the time

`pyproject.toml` sets `timeout = 300` with `timeout_func_only = true`, which
restricts the timer to the call phase and leaves fixture setup and teardown
untimed. Fixture setup totals 6h46m42s across a full run and individual setups
reach 6m05s, so the only phase that can hang unboundedly is the only phase with
no deadline. A 4m57s setup passed silently; one that never returned would be
indistinguishable until the job-level timeout killed the lane, naming no fixture.
The open issue on `AdvisoryLockTimeoutError` pre-emption observes the same
setting failing in the opposite direction.

### hardcoded-sleep-windows | medium | Wall-clock sleeps are hand-picked constants

`src/vaultspec_core/mcp_server/tests/test_watchdog.py` carries 19 `time.sleep`
calls, of which these are parent-side and therefore real elapsed time: 20s
(`:304`), 18s (`:458`), 10s (`:939`), 8s (`:575`), 3s (`:531`), 2s (`:264`,
`:456`). `src/vaultspec_core/core/tests/test_advisory_lock.py:668` holds a lock
for 40s. Several prove a negative - that a process is not reaped within a window

- which genuinely requires elapsed time. The defect is not that they sleep but
  that the windows are literals unrelated to the poll interval under test, so they
  cannot shrink when that interval does and cannot be shown sufficient when it
  grows.

### empty-accepted-adr | medium | An accepted ADR is an unfilled template

`2026-03-23-test-quality-adr` carries status `accepted` and a body consisting
entirely of template placeholder prose. It records no decision, yet it is linked
from `2026-03-23-test-quality-research` and sits in the corpus as though it
governs test quality. A reader assessing decision coverage for test work will
find it, read nothing, and be unable to tell whether coverage exists.

### provisioning-adr-drift | low | The provisioning ADR describes a Windows lane the repository no longer runs

`2026-09-05-provisioning-tests-adr` states that Core's Windows jobs are hosted
and already gate pull requests, rejects a self-hosted Windows leg on that basis,
and records under Consequences that the decision binds Core to hosted Windows
continuing to gate. `.github/workflows/ci.yml` now runs the Windows leg of
`broad-tests` on a self-hosted runner. The repository has adopted the option that
ADR rejected while the record still reads `accepted` and unamended. This bears on
the current work: the self-hosted Windows runner is a shared workstation which
carried 23-25 concurrent runner processes during profiling, making it a material
and undocumented input to the 46-minute Windows lane time.

## Recommendations

- Fix the shared state behind the two isolation failures before adopting
  parallelism, rather than pinning the tests together to hide them. No decision
  is required; this is execution.
- Decide how the watchdog cohort is isolated from a parallel runner. The choice
  between a same-worker group and a dedicated serial lane is architecturally
  significant because it constrains every future process-lifecycle test, and
  belongs in the ADR governing this work.
- Decide the durability contract of the shared write path. Whether
  `atomic_write_bytes` owes power-loss durability in every context, or only in
  production, is a commitment other write surfaces will be read against; it is
  the decision this performance work depends on and it is unrecorded today.
- Triage the two failing discovery guards separately from the performance work.
  The fix is to the guarded content or the guard, not to the harness.
- Reconsider the timeout configuration as a whole, covering both phases and both
  failure directions, rather than adjusting one bound.
- Derive the watchdog sleep windows from the poll interval under test, but only
  where doing so does not weaken the property being proved.
- Supersede or complete `2026-03-23-test-quality-adr`. Not blocking here, whose
  coverage is assessed independently, but it is a live trap for the next reader.
- Amend `2026-09-05-provisioning-tests-adr` to record the move to a self-hosted
  Windows leg and why. Out of scope for the performance plan; raised so it is not
  lost.
