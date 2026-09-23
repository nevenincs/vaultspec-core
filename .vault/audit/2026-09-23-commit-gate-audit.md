---
tags:
  - '#audit'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:737398d1829aee7853d7c49fdb11c3939c231d731b35175114188b200230ae8e'
related:
  - "[[2026-09-23-commit-gate-plan]]"
  - "[[2026-09-23-commit-gate-adr]]"
---

# `commit-gate` audit: `plan-close review of the staged commit gate`

## Scope

Plan-close review of `2026-09-23-commit-gate-plan` (L1, Steps S01-S09) against
`2026-09-23-commit-gate-adr`, covering commits `dd6a0fd1..2f649ee7` on `fix/commit-hook`:
the earlier opt-out fixes (doctor, migrate, lock sentinels, sanitize-hook retirement) and
every plan Step. The independent `vaultspec-code-reviewer` persona ran the review. It traced
upgrade convergence, real prek commits, subset equivalence, the provider guard, declined and
`.yml` workspaces, output advice, and doc accuracy.

Result of this review: REVISION REQUIRED (one high finding).

Verified clean:

- **Equivalence:** the staged pass over all of this repository's vault documents matched
  `run_all_checks` exactly for the twelve admitted checkers.
- **CRLF:** working-tree and blob text normalise identically.
- **Convergence:** `sync` converged a `.yml` workspace carrying the three retired hooks in
  place, kept the operator's own hook, and listed only the `.yml` sentinel.
- **Real prek 0.5.3 commits:** an introduced error blocked and an inherited one did not.
  Deletion-only commits, paths with spaces, detached HEAD, a first commit and a
  non-repository directory all behaved.
- **Pruning:** removes only zero-byte sentinels.
- **Boundary:** no source, doc or config line cites a vault document or issue id.

## Findings

### declined-migrate-deletes-operator-config | high | `migrate --remove-yaml` in a declined workspace deletes a hook config carrying third-party hooks

`src/vaultspec_core/core/prek_boundary.py:366-386` unlinks the leftover YAML in the declined
branch without checking what it holds, even with no `prek.toml`. Reproduced: after
`spec precommit disable`, `migrate --remove-yaml` deleted a config whose other entry was an
operator `ruff` hook. `src/vaultspec_core/cli/spec_cmd_doctor.py:545-551` recommends exactly
that command for `DECLINED_LEFTOVER`. Uninstall (`src/vaultspec_core/core/uninstall.py:160-190`)
strips managed ids only, which is the safe precedent. Reopens S04.

### provider-guard-blocks-declined-config | medium | a declined workspace's operator-authored hook config is reported as a per-machine file

`src/vaultspec_core/core/git_artifacts.py:356-378` takes the whole managed ignore set, which
`src/vaultspec_core/core/gitignore.py:288-289` extends with both YAML spellings when hooks are
declined. Reproduced: a staged hand-written `.pre-commit-config.yaml` made `commit-gate` exit 1
as "per-machine". The config is neither per-machine nor vaultspec's. S05.

### head-attribution-desync | medium | a non-blob entry at HEAD desynchronises the cat-file stream and drops every later baseline

`src/vaultspec_core/vaultcore/checks/staged.py:157-168` does not advance past a non-blob
object's payload, so later headers are parsed from inside content. Reproduced with a
`.md`-named tree at HEAD: both documents lost their baseline, so inherited errors would block.
The unguarded `out.index` can raise. S02.

### stale-installed-reference | medium | the tracked `.vaultspec/reference/cli.md` projection still names `spec-check` as the pre-commit gate

`.vaultspec/reference/cli.md:794-796` was not re-synced after S09 updated
`src/vaultspec_core/builtins/reference/cli.md`, and CI does not diff the projection. S09.

### init-leftovers | medium | `dev/init/hooks.py` is unreachable and two init docstrings still say init installs git hooks

No caller remains after `dev/init/plan.py` dropped the step. `dev/init/__main__.py:24-26` and
`dev/init/contract.py:31-33` describe hook installation. S03.

### gate-output-on-unresolved-workspace | low | `commit-gate` prints an error and an unrelated home-directory hint, then exits 0, when it cannot resolve a workspace

`src/vaultspec_core/cli/root_commit_gate.py:88-90` via `resolve_effective_target`. S07.

### stale-comments | low | three modules explain behaviour by naming hooks that no longer exist

`src/vaultspec_core/vaultcore/checks/structure.py:287`,
`src/vaultspec_core/core/diagnosis/collectors_provider.py:43`,
`src/vaultspec_core/cli/spec_cmd_doctor.py:957`. S08.

### nested-workspace-fails-open | low | with the workspace below the git root, staged paths do not resolve and the gate checks nothing

`src/vaultspec_core/core/git_artifacts.py:320-353` returns repo-root-relative paths that
`src/vaultspec_core/vaultcore/checks/staged.py:76-79` joins to the workspace root. The layout
was never supported (prek reads the root config, and the old guard shared the limitation).
Recorded; no Step reopened.

### rename-loses-baseline | low | a pure rename has no HEAD blob at its new path, so inherited findings block

`src/vaultspec_core/vaultcore/checks/staged.py:130-168`. This is the ADR's stated behaviour for
renamed documents. Recorded as a known limit; `git diff --cached -M --name-status` would supply
the source path if it is revisited.

### rereview-after-fixes | low | re-review of commits `bc8b251f..f95b1525` passes; one comment overstated what the gate skips

The same reviewer verified each fix against a real workspace:

- **Declined `--remove-yaml`:** strips only managed hooks, keeps the operator's hooks and
  comments, and dry-runs without writing. A managed-only config is still deleted, and one
  without vaultspec hooks is untouched.
- **Guard:** lets a declined workspace's own config through, while a staged install manifest
  still blocks.
- **Committed-version read:** keeps the following document's baseline when a path is a tree
  at HEAD, and handles missing paths, spaces, no `HEAD` and bad refs without raising.
- **Earlier findings:** `init` leftovers, gate output, stale comments and the `NOT_INSTALLED`
  resolver change are all correct. The subset equivalence still matches the full pass
  exactly over this repository's vault, and real prek commits still block as intended.

The stale-installed-reference finding was withdrawn. The deployed mirror consistently
describes the released 0.2.4, and it is refreshed from the packaged builtins after each
release. The next carry-forward must pick up the `commit-gate` entry and the
`--gate-errors` rewording.

The one new low finding: the comment in `src/vaultspec_core/cli/root_commit_gate.py` said
that nothing is gated outside a workspace, but only the context setup is skipped there. It
was reworded, and a mid-sentence docstring wrap in `dev/init/__main__.py` was reflowed.

Result: PASS. The plan is complete.

### s10-crlf-normalisation | medium | the unattended migration rewrote a CRLF `prek.toml` to LF and added a trailing newline

The review of S10 found that `src/vaultspec_core/core/prek_boundary.py`, via
`_replace_or_append_block`, re-emitted every line outside the markers with LF, so the
release migration produced a whole-file diff on a CRLF checkout. Fixed in `8f98ded1`:
`prek.toml` is read as bytes and rewritten with its own terminator and final-newline state.
The regression test is in `src/vaultspec_core/migrations/tests/test_commit_gate.py`.

### s10-unreadable-yaml-called-clean | low | an unparseable YAML config was reported as carrying no vaultspec hooks

`managed_strip_outcome` returned `"unchanged"` for a parse failure. Fixed in `8f98ded1` by
adding a separate `"unreadable"` outcome, which the migration and the declined remove path
report.

### s10-refresh-on-invalid-toml | low | the block refresh wrote into a `prek.toml` that the migrate verb refuses as invalid

Fixed in `8f98ded1`: `refresh_managed_prek_block` refuses invalid TOML, and the migration
reports it as unreadable.

Result of the S10 review: PASS. All three findings are fixed and each has a failing-first
test. The reviewer also noted that any later migration shipping in 0.2.5 must target
`0.2.6`, because a workspace converged from this branch already records `0.2.5`.

### s11-unowned-duplicate-unrepairable | medium | a prek.toml duplicate outside vaultspec's markers was an error every repair claimed to handle and none could

The review of S11 found that with the canonical hook hand-written twice and no managed block:
doctor exited 2 and pointed at `spec precommit migrate`, `migrate` answered `unchanged`, and
`sync` and the repair executor silently did nothing. Fixed in S11 follow-up work: the new
`unowned_duplicate` check in `src/vaultspec_core/core/prek_boundary.py` answers from the file
without writing. With it, `migrate` reports `conflicting` and exits 1, `sync` and the executor
warn via `repair_managed_prek_block`, and doctor's text names hand-written copies as the
operator's to remove.

### s11-emptied-first-local-repo | low | the dedupe left an emptied first local repo behind as `hooks: []`

Fixed: `_reconcile_precommit_repos` now drops any local repo the merge itself emptied,
including the first, and keeps an empty stanza the operator wrote.

### s11-amendment-ahead-of-approval | low | the duplicate-listings amendment sat in the accepted ADR while its design question was unanswered

Resolved by moving the decision into the proposed
`2026-09-23-commit-gate-duplicate-listings-adr` and restoring the accepted record to its
authorized content. The plan records that S11 executed ahead of that record's acceptance.
Acceptance is now the user's to give.

Result of the S11 review: PASS. The medium and the first low are fixed with failing-first
tests; the second low awaits the user's acceptance of the proposed record.

## Recommendations

- declined-migrate-deletes-operator-config: in the declined branch, delete a config only when
  it carries nothing but managed hooks; otherwise strip the managed ids and keep the file.
- provider-guard-blocks-declined-config: give the guard its own subset of the managed
  entries, excluding the declined hook-config lines. Whether "ignored by the managed block"
  and "must never be staged" should be one set or two is a decision for a follow-on ADR.
- head-attribution-desync: skip every object's payload by its size, and treat a malformed
  header as "no baseline" for the remaining paths.
- Add a test that the baseline pass writes nothing to disk.
- `_LinkIndex` is rebuilt per process. A commit large enough for the runner to split into
  several invocations walks the vault once per invocation; measure before it matters.
