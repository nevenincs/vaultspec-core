---
tags:
  - '#audit'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:42d1286ca28767c15621a4f3668ecb47a9fed60f8cb32f4a0482128c855b6d7d'
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

### crash-attribution-correction | high | Two earlier findings misread four worker crashes as six defects

Correcting `test-isolation` and `watchdog-self-termination` above, both of which
were written from the same misreading and are superseded by this entry.

The parallel run's FAILURES section reports four workers crashed - gw1, gw4,
gw8, gw11 - each naming the test in flight at the moment it died:
`test_lock_sentinel_policy`, `test_collectors`, `test_doctor` and
`test_antigravity_agents`. Those four names then reappear in the short summary
as FAILED. They are one event counted twice, not two crashes plus two assertion
failures. The named tests pass serially because nothing is wrong with them; they
were running on workers that died.

The mechanism given in `watchdog-self-termination` is also wrong.
`src/vaultspec_core/mcp_server/watchdog.py` **self-reaps**: it concludes its own
process is orphaned and exits. It does not walk up and terminate an ancestor, so
"the ancestor is the xdist worker" describes something the code does not do. The
one test that arms in-process, `test_kill_switch_disables_arming_in_process`,
sets the kill switch first precisely so no watchdog thread is spawned inside the
runner, and says so in its docstring.

What is established: four workers died during a 12-way run, and the four
reported failures are those deaths. What is not established is why. The run was
on a workstation concurrently executing this repository's own self-hosted CI at
100% CPU, which the original findings did not weigh and which makes resource
exhaustion a live alternative to anything test-specific.

The two genuine assertion failures in that run were both in
`test_discovery_guidance.py`, from wording drift between `not installed` and
`unavailable`, unrelated to parallelism and since fixed on `main`. That leaves
`failing-guards-on-main` above accurate as written.

### durability-is-observable-in-one-cohort | high | The fsync boundary changes a concurrency test's subject

Found by executing the decision rather than by reading it, and it is the
boundary's own rule firing on the boundary.

`src/vaultspec_core/vaultcore/tests/test_fix_writer_concurrency.py` races a
writer thread against a `--fix` pass and asserts no committed edit is lost. That
makes the timing of the atomic-write path the thing under test, not incidental
to it. Suppressing `os.fsync` tightens the write loop enough to exhaust
`_WINDOWS_REPLACE_RETRY_BUDGET_SECONDS`, the 2s budget `_replace_atomic` spends
riding out a Windows scanner's momentary handle on the destination.

Measured, 20 runs of the same test on the same machine:

| condition        | result         |
| ---------------- | -------------- |
| fsync suppressed | 4 failed of 20 |
| fsync restored   | 0 failed of 20 |

The failure is real, not a masking artefact: `atomic_write` raises `WinError 5`
after exhausting its retries, the edit is genuinely discarded, and the test
correctly reports a lost write.

So this cohort can observe the suppression, which is exactly the condition the
governing decision excludes. It is handled by a narrow `durable` marker that
hands those tests the real call back, not by abandoning the boundary, because
the no-observation property still holds everywhere else in the suite.

There is a second, product-facing reading worth separating from the test fix: a
2s replace-retry budget is sufficient against a writer that fsyncs between
attempts and marginal against one that does not. Nothing establishes that a real
caller writes as fast as this stress loop, so this is an observation about the
budget's headroom rather than a defect, and it is recorded here rather than
acted on.

### plan-close-review | low | The integrated result holds, with two Steps deliberately unexecuted

Review at plan close, covering the change as one behaviour rather than file by
file: the durability boundary, the workspace reuse, the parallel lanes, and the
guards that hold each in place.

**Measured outcome.** On an idle host, `just test-broad` runs 4421 tests in
3m57s; `test-harness` 340 in 3.7s; `test-repo` 131 in 45.9s. The starting point
was 36 minutes on Linux and 46 on Windows. Fixture time across a full run fell
from 6h46m42s to 13m45s. No xdist worker was lost in any of the three runs made
after the boundary landed.

**The behaviour holds where it matters.** The reuse is equivalence-checked rather
than assumed: `test_workspace_template_reuse.py` compares a copied tree against a
built one, asserts no path still points at the template, and asserts the two
narrow cases - a seeded directory, a single-provider install - still run the real
product. `test_durability_boundary.py` holds the divergence to the harness. The
`durable` marker's evidence is recorded with its measurement rather than its
intuition.

**Two decisions changed under evidence during execution**, both recorded above:
the crash attribution was retracted after re-reading the run output, and the
boundary's own no-observation rule caught a cohort it did not hold for. Neither
is a defect in the delivered change; both are the reason the delivered change can
be trusted.

**Not executed, deliberately.** `P05.S12` (a deadline on fixture setup) was
attempted twice and backed out: both mechanisms corrupt pytest's fixture
bookkeeping, and shipping a harness that breaks 133 guards to catch a
hypothetical hang is a worse trade than leaving the gap documented. `P05.S13`
(deriving the watchdog sleep windows) was dropped because after the other Phases
those tests no longer appear in the lane's fifteen slowest entries, making the
change churn on the most delicate process-lifecycle tests in the suite for no
measurable gain. Both are recorded in the ledger and in issue #514.

**One failure remains in the lane**, `test_vault_edit.py::TestSetBody::test_stdin_channel_preserves_legacy_c1_byte`,
reproduced identically on `b5c7f256` under the same environment and filed as
issue #518. It is a real product question about the `--body-stdin` channel, not a
consequence of this work, and is out of its scope.

### parallelism-destabilises-the-contention-cohort | high | Enabling the runner made the concurrency stress tests flaky

Found by running the lane repeatedly instead of once, which is the only way this
class of defect shows up at all.

Three consecutive full runs under `-n auto` produced two failures, each in a
different test whose subject is behaviour under contention:

- `test_rename_concurrency.py::test_no_deadlock_under_concurrent_rename_and_edit_load`
  - `PermissionError(13)` under load
- `test_fix_writer_concurrency.py::test_concurrent_edit_survives_a_fix_pass` - a
  committed edit discarded

The same two modules run 6/6 green single-process. The failures are the Windows
replace-retry budget being exhausted by disk traffic the tests did not create:
eleven other workers saturating the same volume.

This is the same shape as `durability-is-observable-in-one-cohort` above and
generalises it. A test that races two writers and asserts no write is lost is
measuring the product's locking; run it beside eleven unrelated workers and it
measures the host instead. The `durable` marker fixed one input to that
measurement (fsync); it could not fix the other (everything else on the box).

Note that the earlier retraction still stands and this is not a return to it:
those four worker deaths were whole-process crashes with no assertion, whereas
these are ordinary assertion failures in a named test. Different signature,
different cause.

Handled by a `serial` marker and a second single-process pass in the `test`
lanes, rather than an xdist group: a group pins the cohort to one worker and
leaves the other eleven hammering the volume, which is the thing that breaks it.
47 tests carry it - the two dedicated concurrency modules plus the
contention-timing classes in `test_advisory_lock` and `test_edit_engine`.

### fast-gate-was-the-slowest-lane | high | `test-unit` never got the worker count the other lanes got

Found by timing every lane rather than the one under change.

`test-unit` describes itself as "the fast marker-scoped gate". It ran 1845
tests in **7m20s**, single-process, while `test-broad` ran 4375 in four minutes.
The parallel worker count had been wired into `broad`, `harness` and `repo` and
not into `unit`, so the lane's name and its behaviour had come apart - and it
was the lane a contributor is most likely to run before pushing.

Split the same way as `broad`, a parallel pass plus a single-process pass for
the contention cohort: **7m20s to 55s**.

The general lesson is the one this campaign keeps re-learning: a change wired
into the lanes you are looking at is not wired into the lanes you are not. The
audit's own recommendation to re-measure repeatedly should extend to
re-measuring *everything*, not the thing just edited.

### settled-numbers | low | Where the lanes came to rest

Five measurements of `broad` and two full sweeps of every lane, on a host that
intermittently runs this repository's own self-hosted CI:

| lane           | time             | population                |
| -------------- | ---------------- | ------------------------- |
| `unit`         | 51-71s           | 1906-1925                 |
| `broad`        | 232-301s typical | 4375 parallel + 47 serial |
| `harness`      | 4-8s             | 340                       |
| `repo`         | 55-57s           | 131                       |
| `vault-repair` | 5-9s             | 29                        |

Against 36 minutes on Linux and 46 on Windows at the start.

The residual spread is the host, not the suite: the slowest `broad` observation
(430s) was taken with a CI job running beside it, and the fastest (232s) on an
idle box. Test-level flakiness is gone - the contention cohort has now passed
47/47 in five consecutive runs, against two failures in three before the split.

The fixture leaderboard is flat. `synthetic_project` is 406 uses at a 519ms
median, which is a 245-file copy under 24-way load (189ms uncontended); the next
fixture is 48s total and everything after it is under 18s for a whole run. No
fixture is doing work its tests do not need. The three that still run a real
install - `test_ambiguous_states`, `test_preflight`, `test_executor` - each seed
a `.gitignore` first, so the reconciliation is the precondition under test.

### phase-five-close | low | PASS - timing blind spots are bounded without custom pytest hooks

Review at Phase P05 and plan close. Pytest-timeout's supported whole-test mode
now covers setup and teardown while retaining the 600-second budget held above
the advisory-lock waits by `dev/guards/test_automation_contracts.py`. A forced
50ms run failed inside the active `tmp_path` fixture stack, and the normal
focused run completed without disturbing fixture finalisation. The watchdog
suite derives its default observation window from `_POSIX_POLL_SECONDS` and its
compressed cases from their explicit grace, rearm, and confirmation inputs;
all real-process lifecycle cases pass. No critical or high findings remain.

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

- Establish why four workers died before enabling parallelism, treating the
  cause as unknown rather than assumed. The earlier recommendation to decide how
  to isolate the watchdog cohort rested on a mechanism this audit has since
  retracted, and acting on it would have contained a cohort that may have
  nothing to do with the crashes.

- Re-run the parallel measurement on a machine not simultaneously executing this
  repository's CI, so resource exhaustion can be excluded or confirmed before
  any test is blamed.

- Keep the `durable` opt-out narrow and evidence-backed. A marker applied
  because a test is flaky, rather than because the suppression provably changes
  what it measures, would turn the boundary's rule into a formality.

- Consider separately whether `_WINDOWS_REPLACE_RETRY_BUDGET_SECONDS` has enough
  headroom for a fast writer. This work has no evidence that a real caller
  reaches that rate, so it is a question rather than a finding.

- Keep the `serial` cohort defined by what a test MEASURES, not by whether it
  has been seen to flake. A marker applied to whatever failed last is a
  quarantine list; this one has to stay a statement about the test's subject or
  it will absorb real defects.

- Re-run any future parallelism change several times before believing it. A
  single green run does not distinguish a stable lane from a lane that fails one
  time in three, and this campaign would have shipped the difference.
