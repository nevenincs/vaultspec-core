---
tags:
  - '#audit'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:db31addfafa5d2458847c34ed4b15b072f425750df899e4949958929c772b76a'
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
