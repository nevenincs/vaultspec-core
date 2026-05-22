---
tags:
  - '#research'
  - '#test-framework-hardening'
date: '2026-05-17'
related: []
---

# `test-framework-hardening` research: `scope and prior-art for the test framework audit`

The vaultspec-core test framework is a candidate for a hardened audit sweep
targeting four anti-patterns: tautological tests, mocks/patches, fakes/stubs,
and tests that re-implement business logic instead of exercising the
implementation directly. This research scopes the audit, records what the
existing meta-tests already enforce, and identifies the gaps that a deeper
semantic sweep must cover.

## Findings

### Test surface

The combined test corpus carries ninety-eight test modules and roughly
twenty-six thousand lines of test code, spread across:

- `src/vaultspec_core/tests/cli/` (thirty-seven modules; the largest cluster,
  covering CLI command surfaces and provider plumbing)
- `src/vaultspec_core/tests/plan/` (thirteen modules; plan parser and
  identifier contracts)
- `tests/` (eleven top-level modules; cross-cutting contracts and automation)
- `src/vaultspec_core/vaultcore/tests/` (eight modules; vault parsing
  primitives)
- `src/vaultspec_core/vaultcore/checks/tests/` (seven modules; per-check
  rules)
- `tests/mcp/` (three modules; MCP server contracts)
- Smaller clusters under `migrations/tests/`, `core/tests/`, `config/tests/`,
  and `testing/tests/`.

The full unit run (`pytest -m "not integration and not e2e"`) reports
1462 passing tests.

### Static contract already enforced

`tests/test_test_suite_quality.py` is a meta-contract that walks every test
module via `ast` and asserts the following are absent:

- Imports of `unittest.mock`, `mock`, or `pytest_mock`.
- The fixture names `monkeypatch`, `mocker`, plus the call names `Mock`,
  `MagicMock`, `AsyncMock`, `patch`.
- The skip / xfail family: `pytest.skip`, `pytest.xfail`,
  `pytest.importorskip`, `pytest.mark.skip`, `pytest.mark.xfail`,
  `pytest.mark.skipif`.
- Calls to `patch` or `patch.object` (the `unittest.mock` decorator form).
- Any class or function whose name contains `fake` or `stub` (case
  insensitive).

A second meta-test in the same module rejects `find('{')`, `index('{')`,
`split('{')`, and `partition('{')` calls on stdout strings, which would
hide human-readable prefixes before a JSON payload is parsed.

The meta-contract currently passes against the full suite, so the four
syntactic anti-patterns the user named (mocks, fakes, stubs, patches plus
skips) are statically guaranteed not to exist anywhere in the test tree.

### Gaps the static guard cannot cover

The static guard reasons about syntax. It does not detect:

- Tautological assertions such as `assert x == x`, `assert True`,
  `assert isinstance(x, type(x))`, or any assertion that holds for every
  possible value the subject under test can produce.
- Assertions that only verify "no exception was raised" without inspecting
  the produced state, when the contract under test is that the call also
  produces state-changing output.
- Whitelist patterns that accept multiple exit codes or both branches of a
  boolean as success (`assert exit_code in (0, 1)`).
- Tests whose assertion structure permits the test to pass even when the
  feature being tested is silently broken.
- Tests that reimplement the algorithm under test (re-parse YAML, re-walk
  the AST, re-compose the expected output using the same code path the
  subject under test uses) and then compare the system output to the
  test's own re-implementation. Such tests provide false coverage because
  both sides change together.
- Tests that swallow exceptions via bare `except:` and pass anyway.
- Tests that depend on side-effect ordering or on flaky environment
  conditions that the test does not assert against.

These gaps require semantic review, not syntactic linting. The audit must
walk every test module by hand or via narrow heuristics and judge each
suspect site.

### Heuristic anchors for the audit pass

The following patterns are heuristic anchors that the audit sweep will
look for and triage. They are not strict definitions; each candidate must
be re-read in context to decide if it is a real anti-pattern.

- `assert .* in \(.*,.*\)` where two boolean or two exit-code states are
  whitelisted at once.
- `try:` blocks inside test bodies followed by `except .*: pass` or by an
  unconditional `assert True`.
- Assertions whose right-hand side is computed by importing the same helper
  the system under test imports and running it on the same input.
- Tests whose only assertion is `assert result is not None` or
  `assert len(result) > 0` without further structural checks.
- Tests that pass `dry_run=True` and then assert only on the absence of a
  side effect, when the contract is that `dry_run=True` ALSO produces a
  preview manifest.
- Tests with a `result =` line that is never referenced in an assertion
  thereafter.
- Tests that assert on log-line content as a proxy for the actual behaviour
  the log line was supposed to accompany.

### Scope and pacing

The audit is a separate Wave of the broader vaultspec restructure epic
tracked in issue #115. It begins after the source-layout-collapse PR lands
its first round of review; this research record reserves the feature tag
`#test-framework-hardening` and the heuristic-anchor list above so the
findings document can land with a concrete starting position. The audit
document and any code-level remediation will land in subsequent PR updates.
