---
tags:
  - '#audit'
  - '#vaultspec-source-layout-collapse'
date: '2026-05-17'
related:
  - '[[2026-05-17-vaultspec-source-layout-collapse-adr]]'
  - '[[2026-05-17-vaultspec-source-layout-collapse-plan]]'
---

# `vaultspec-source-layout-collapse` audit: `code review verdict pass with five low-medium findings`

This audit records the independent code review of branch
`claude/reorganize-vaultspec-structure-79P2r` against `main`. The review
covered the nine-commit diff that lands the source-layout-collapse work
authorised by the ADR.

## Verdict

PASS. No CRITICAL or HIGH-severity issues block the merge. The build, the
wheel and sdist contents, the runtime resolver, the gitignore shape, the
diagnosis collectors, and the test suite all align with the plan. Five
findings surfaced at MEDIUM and LOW severity; three were closed in a
follow-up commit, one is a pre-existing semantic note, and one was
re-evaluated as a false positive.

## Findings

### LAYOUT-01 - MEDIUM - stale `VAULTSPEC_ALLOW_DEV_WRITES` row in `docs/CLI.md`

The environment-variables table in `docs/CLI.md` carried a row for
`VAULTSPEC_ALLOW_DEV_WRITES`, an override that bypassed the
development-write guard. The bypass mechanism itself had already been
retired on `main` before this branch was opened, so the row described a
contract that no longer existed in code. Because this PR is the natural
moment to clean up dev-mode documentation surface, the row should not
ship.

**Status**: CLOSED. The row was removed from `docs/CLI.md` in the same
commit that addresses the other actionable findings.

### LAYOUT-02 - MEDIUM - pre-commit wrapped-markdown regex undershoots `docs/`

`.pre-commit-config.yaml` hard-coded the three known documents
(`docs/(framework|MCP|CLI)\.md`). The local `justfile` target
`_dev-lint-markdown` runs `mdformat ... docs/` recursively, so any future
nested document under `docs/sub/foo.md` would be checked locally but
skipped by the pre-commit hook. The two surfaces should agree on the
corpus.

**Status**: CLOSED. The regex was broadened to `docs/.*\.md` so the
pre-commit hook and the justfile linter cover identical corpora.

### LAYOUT-03 - LOW - `src/vaultspec_core/builtins/rules/.gitignore` shipped in the wheel

The bundled rules tree carries a `.gitignore` that says
`*.md / !*.builtin.md`. The auditor flagged the file as residual because
"there is no git inside a Python package".

**Status**: NO ACTION. Re-evaluation shows the file is deliberately
shipped: `seed_builtins` copies the entire subtree into the consumer's
`.vaultspec/rules/rules/` during install. There, the file enforces the
canonical custom-rule convention (consumer-authored `*.md` rules are
gitignored; framework-bundled `*.builtin.md` rules are tracked).
Deleting it would change established consumer behaviour. The file's
incidental presence inside the package source tree is a storage
artefact, not a contract violation. Documented here so future audits do
not re-flag.

### LAYOUT-04 - LOW - `_workspace_ctx` reset example pattern moved with deleted tests

`src/vaultspec_core/core/tests/test_guard_plumbing.py` carried a
documented autouse fixture that demonstrated the `ContextVar`-token
reset pattern used to keep `install_run` re-entrant under pytest. The
pattern itself is still in use at
`src/vaultspec_core/tests/cli/conftest.py` and is exercised by the
sync-manifest test suite, so no contract regresses.

**Status**: NO ACTION. The contract is preserved; only a particularly
clean example of the pattern moved out with the deleted test module.
The example remains recoverable from git history at commit `d54d5eb~1`
if a future test needs the same scaffolding.

### LAYOUT-05 - LOW - upgrade foot-gun on legacy consumers with committed `.vaultspec/`

The new gitignore contract treats `.vaultspec/` as a pure install
artefact and emits the bare directory entry from `get_recommended_entries`.
On `install --upgrade`, `_untrack_managed_paths` will iterate every
managed entry and call `git rm --cached`. A legacy consumer that
committed their entire `.vaultspec/` tree before the framework declared
it install-only will see the whole tree untracked on the first upgrade
after this PR merges. The behaviour is correct by ADR design (the source
of truth for bundled content moved into the wheel) but represents a
visible behavioural change.

**Status**: NO CODE ACTION. The contract is intentional and correct.
The next release note should call this out so operator surprise is
contained at deploy time rather than discovered post-merge.

## Mandate-by-mandate verdict

The review covered seven mandates listed in the audit charter. Verdicts
recorded below for the file-by-file record.

- **Semantic regressions**: none. Removing `guard_dev_repo` does not
  open a foot-gun; the multi-signal detector previously distinguished
  source repos from consumers, but both now follow the same code path
  and produce equivalent outcomes (install creates `.vaultspec/`,
  gitignore covers it, doctor reports `ok`).
- **Hidden dependencies**: none. A repository-wide grep returns zero
  hits for `guards`, `guard_dev_repo`, `is_dev_repo`,
  `DevRepoProtectionError`, `_cached_is_dev_repo`, `--dev`, or
  `dev_mode` (excluding the unrelated `uv sync --dev` invocation in
  an unrelated agent persona body).
- **Test coverage gaps**: none introduced. The deleted test files
  exercised only the dev-mode contract; no orphan contract survives.
- **Build and packaging**: clean. `uv build` produces a wheel that
  ships forty-three files under `vaultspec_core/builtins/` exactly
  matching the inventory. The publish workflow guard correctly
  retargets at `src/vaultspec_core/builtins/templates`.
- **Plan fidelity**: verified. P06.S41 / S42 / S43 were correctly
  closed without code change: the three files cited in those Steps
  operate on tmp consumer-fixture roots, not on dev-repo canonical
  paths.
- **Documentation consistency**: clean after LAYOUT-01 closure. No
  `.vaultspec/CLI.md`, `.vaultspec/MCP.md`, or `.vaultspec/README.md`
  references remain anywhere. The bundled rule references point
  correctly at GitHub URLs.
- **Acceptance criteria from the grounding issue**: satisfied by the
  ADR plus plan plus verification commit chain.

## Verification re-run after fixups

After the LAYOUT-01 and LAYOUT-02 closures landed:

- 1462 unit tests pass.
- `vault check all` is silent (zero warnings).
- `prek run --all-files` passes every hook except `taplo-lint` (binary
  unavailable in the verification sandbox; unrelated to the diff).
- `vault plan check` is silent on the plan document.
- `uv build` produces a wheel and sdist with the expected layout.
- `vaultspec-core install` against the dev repo succeeds without
  `--dev` and `spec doctor` reports `framework: ok`.

## Recommendation

Approve and merge. LAYOUT-01 and LAYOUT-02 closures landed in a
follow-up commit; LAYOUT-03 is documented as deliberate; LAYOUT-04 has
no actionable contract regression; LAYOUT-05 is queued for the next
release note.
