---
tags:
  - '#audit'
  - '#test-framework-hardening'
date: '2026-05-17'
related:
  - "[[2026-05-17-test-framework-hardening-research]]"
---

# `test-framework-hardening` audit: `semantic sweep findings and remediation`

The audit sweep dispatched four parallel haiku Explore agents against the
four anti-pattern categories the static contract in
`tests/test_test_suite_quality.py` cannot detect:

- Category 1: tautological assertions.
- Category 2: weak assertions that whitelist multiple outcomes.
- Category 3: tests that re-implement business logic to derive expected
  values.
- Category 4: tests that swallow exceptions or omit half of a behavioural
  contract (dry-run side-effect verification, caplog level, capsys
  stderr).

Two categories returned zero findings. Two categories returned thirteen
candidate sites. After in-context triage thirteen distinct sites
remained for action across nine files; two of the original sites were
re-classified as false positives and one as a documented version-quirk.

## Verdict

Test framework is structurally sound. The static guard already enforces
the four named syntactic anti-patterns. The semantic sweep surfaced one
genuinely high-severity weakness (a test that accepts a crash exit code
as success) and a cluster of weak exit-code-whitelisting patterns whose
real fix is to assert the deterministic expected state rather than
accept either branch.

## Findings by category

### Category 1 - tautological assertions - CLEAN

The agent walked every assertion across ninety-eight test modules and
reported zero literal tautologies, zero `x == x` patterns, zero
`isinstance(x, type(x))` patterns, and zero missing assertions on
computed values. The structural `assert len(x) > 0` and
`assert result is not None` checks the agent observed all serve as
guards before subsequent indexing or attribute access; none stand alone
as the only assertion in a test.

### Category 2 - weak / whitelisting assertions - NINE FINDINGS

#### TEST-01 - HIGH - `test_audit_coverage.py:391` accepts a crash exit code as success

The test asserts `result.exit_code in (0, 1, 2)` for the V1 manifest
doctor pathway with a docstring claiming "should not crash". Exit code
two is the Typer crash signal: this assertion accepts the failure mode
the test claims to prevent.

**Status**: CONFIRMED. Remediation: assert `result.exit_code in (0, 1)`
and additionally assert on the v1-handling diagnostic line in
`result.output`.

#### TEST-02 - MEDIUM - `test_hostile_filesystem.py:142,158,170,194` whitelists exit codes after recovery

Four sites exercise `sync --force` and `spec doctor` recovery from
corruption and assert `exit_code in (0, 1)`. The recovery contract is
deterministic for each test scenario, so the test should pick the
specific expected branch and assert it. Accepting either branch lets a
silent regression in the recovery flow pass.

**Status**: CONFIRMED. Remediation: pick the expected branch per test
scenario; add positive assertions on the rendered diagnostic state
(manifest repaired, no remaining warnings, etc.) so the exit code is
not the sole signal.

#### TEST-03 - MEDIUM - `test_main_cli.py:102` and `test_integration.py:26` whitelist on the synthetic corpus

Both tests run `vault check all` against the synthetic project fixture
and accept either zero or one. The synthetic corpus is a fixed input;
the right answer is whichever the corpus produces deterministically. If
the corpus carries known warnings the test should assert the warning
text appears in output.

**Status**: CONFIRMED. Remediation: pin the expected exit code and
assert on a stable identifier of the diagnostic block.

#### TEST-04 - MEDIUM - `test_doctor.py:25` whitelists on a freshly-installed workspace

The test runs `spec doctor` on a workspace immediately after a clean
install and accepts exit code zero or one. A clean install is the
canonical "everything is ok" state; the test should assert exit code
zero and assert that no warnings are surfaced.

**Status**: CONFIRMED. Remediation: assert `exit_code == 0`.

#### TEST-05 - MEDIUM - `test_ambiguous_states.py:212` whitelists on a clean installed workspace

Same shape as TEST-04. The fixture `installed_workspace` is a clean
install; the deterministic answer is zero.

**Status**: CONFIRMED. Remediation: assert `exit_code == 0`.

#### TEST-06 - MEDIUM - `test_ambiguous_states.py:223,236,251` use OR-logic across exit code and output

Three sites assert `exit_code != 0 or "<keyword>" in output`. The
disjunction permits the test to pass even when the diagnostic message
is absent (whenever the exit code branch is true) or when the exit
code is zero (whenever the keyword appears). The contract is "the
degraded state must be REPORTED"; both branches need to hold.

**Status**: CONFIRMED. Remediation: split into two unconditional
assertions: the keyword must appear in the rendered output, and the
exit code must reflect the diagnostic state appropriate to that
degradation.

#### TEST-07 - LOW - `test_vault_cli.py:353` whitelists `(0, 2)` on a Typer no-args invocation

The comment explains that `no_args_is_help=True` returns zero or two
depending on Typer version. The behaviour is genuinely
version-dependent in older Typer releases.

**Status**: DOCUMENTED. Remediation: tighten to assert on the
"Usage:" rendering (which is the actual contract) and drop the exit
code whitelist; the rendering proves the help branch fired.

#### TEST-08 - FALSE POSITIVE - `test_global_options.py:19`

Auditor's own re-read confirmed the test already pairs
`exit_code != 0` with `"no such option" in result.output.lower()`,
satisfying the contract. No action required.

### Category 3 - algorithm-mirroring tests - CLEAN

The agent surveyed plan, sync, collector, vaultcore, and CLI test
clusters for tests that re-derive expected values by importing the
same helpers the system under test uses. Two near-misses surfaced and
both passed inspection: `test_audit_coverage.py:45,56` reads back the
manifest the system under test wrote, which is structural verification
not algorithmic mirroring; `test_sync_collect.py:58` uses a glob to
verify fixture setup, not to compute an expected result.

### Category 4 - swallowed exceptions and dry-run gaps - FOUR FINDINGS

#### TEST-09 - LOW - `test_registry.py:282` `pytest.raises(RuntimeError)` without `match=`

The test calls `run_pending_migrations` with a single-element registry
whose only failure mode is the helper-injected RuntimeError. Absence
of `match=` is defensible because the test scope is narrow, but adding
the matcher costs nothing and locks the contract.

**Status**: CONFIRMED. Remediation: add
`match="broken intentionally failed"`.

#### TEST-10 - LOW - `test_registry.py:291` `pytest.raises(RuntimeError)` without `match=`

Identical shape to TEST-09 in a sibling test.

**Status**: CONFIRMED. Remediation: add the same match argument.

#### TEST-11 - LOW - `test_config.py:151` caplog assertion omits level check

The test asserts `"below minimum" in caplog.text` for an out-of-range
buffer size. The source emits via `logger.error` in
`src/vaultspec_core/config/config.py:248`, so the contract is an
ERROR-level message. The current assertion would pass if the
implementation downgraded the log to WARNING or INFO.

**Status**: CONFIRMED. Remediation: assert that at least one record
with the matching message has `levelname == "ERROR"`.

#### TEST-12 - LOW - `test_vault_repair.py:661,684` capsys reads only stdout

Two tests capture only `.out` from `capsys.readouterr()` and assert on
the rendered repair-run output. The contract for `_render_repair_run`
is to write to stdout; stderr should be empty. Adding
`assert captured.err == ""` is a one-line guard against future
regressions that introduce stray warnings.

**Status**: CONFIRMED. Remediation: hold the return value of
`readouterr()` once and assert on both `out` and `err`.

#### TEST-13 - FALSE POSITIVE - `test_audit_coverage.py:427-433` symlink platform probe

The pattern catches `OSError` from `symlink_to` and re-raises as
`AssertionError("This platform must allow ... do not hide filesystem
coverage with a runtime skip")`. The intent is explicit: this test
must NOT silently skip on a platform that lacks symlink support; if
the symlink call fails, the test must fail loudly. The `from exc`
chain preserves the OSError context. This is the right pattern, not a
swallow.

**Status**: NO ACTION.

## Remediation summary

Twelve sites across eight files require code changes:

- `src/vaultspec_core/tests/cli/test_audit_coverage.py` - TEST-01.
- `src/vaultspec_core/tests/cli/test_hostile_filesystem.py` - TEST-02
  (four sites).
- `src/vaultspec_core/tests/cli/test_main_cli.py` - TEST-03 (one
  site).
- `src/vaultspec_core/tests/cli/test_integration.py` - TEST-03 (one
  site).
- `src/vaultspec_core/tests/cli/test_doctor.py` - TEST-04.
- `src/vaultspec_core/tests/cli/test_ambiguous_states.py` - TEST-05
  and TEST-06 (four sites).
- `src/vaultspec_core/tests/cli/test_vault_cli.py` - TEST-07.
- `src/vaultspec_core/migrations/tests/test_registry.py` - TEST-09
  and TEST-10.
- `src/vaultspec_core/config/tests/test_config.py` - TEST-11.
- `src/vaultspec_core/tests/cli/test_vault_repair.py` - TEST-12 (two
  sites).

The remediation lands as a single commit on the same branch; the audit
document records the closure rationale per finding above.

## Verification

After remediation the full unit run must continue to report 1462
passing tests (or higher if a remediation surfaces a previously-hidden
real defect). The remediation must not introduce any new mocks, fakes,
stubs, patches, skips, or xfails (the static contract will catch them
if it does).
