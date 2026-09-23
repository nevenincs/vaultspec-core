---
tags:
  - '#plan'
  - '#commit-gate'
date: '2026-09-23'
tier: L1
related:
  - '[[2026-09-23-commit-gate-adr]]'
  - '[[2026-09-23-commit-gate-duplicate-listings-adr]]'
modified: '2026-09-23'
body_schema: body-v2
body_hash: 'sha256:4bd1ec689ce85e315a6e6da7f802d22524d2d38cb8572bd2aaf9fd5837b3c7da'
---

# `commit-gate` plan

Replace the three whole-vault commit hooks with one staged-document gate, and stop core's own bootstrap from installing a commit hook.

## Description

Approved 2026-09-23

Basis: on 2026-09-23 the user accepted `2026-09-23-commit-gate-adr`, including the amendment to the sanitize-hook clause of `2026-05-15-template-annotation-sanitization-adr`, and approved this plan. The same instruction directed testing `just init` in an isolated scratch worktree and managing the prek hook install on the live core repository. The work was first directed on 2026-09-23 ("absolutely do that") after the user reviewed the production analysis. The user separately asked on 2026-09-23 that `just init` be fixed too. After the plan closed, the user asked on 2026-09-23 that the hook changes be enrolled in the per-release schema migrations; S10 does that under the amended convergence clause of the ADR. The user then asked that duplicate hook listings be surfaced, as a warning for copies prek does not read and as a repaired error for live duplicates. S11 implements the recommended design recorded in the proposed `2026-09-23-commit-gate-duplicate-listings-adr`. It executed ahead of that record's acceptance because the user's answer to the design question did not arrive, and it is withdrawn if the record is rejected.

Decision coverage:

- `2026-09-23-commit-gate-adr` (proposed) governs S01 and S04 through S09: gate scope, blocking rule, provider guard, output, one canonical hook, convergence, and config resolution in prek's order including `.pre-commit-config.yml`. Its evidence is `2026-09-23-commit-gate-research`.
- S01 applies the ADR's revision to `2026-05-15-template-annotation-sanitization-adr`, retiring that record's canonical sanitize-hook clause. It ratifies commit `981a0c02`. The amendment text is presented with the ADR and applied only once authorized.
- S03 is core's own development tooling, not the scaffolded product. No costly decision is involved and no ADR governs it. It is authorized by the user's request that `just init` be fixed.
- Out of scope: vaultspec-rag's hook config, pushing, merging and releasing. Uninstalling the prek hook already present in core's shared git hooks directory is an operator action awaiting the user's answer, and is not a Step.

Issues addressed:

- S05 fixes #549 (provider guard).
- S07 fixes #550 (no mutating hints).
- S08 fixes #551 (doctor leaves the commit hook).
- S06, S02, S07 and S08 together fix #552 (staged scope and attributable blocking).

## Steps

- [x] `S03` - stop dev init from installing a commit hook, and correct the contributor docs that describe the retired whole-vault and annotation-cleanup hooks; `dev/init/hooks.py, dev/init/plan.py, dev/init/README.md, justfile, docs/framework.md, docs/syntax.md`.
- [x] `S01` - apply the authorized amendment retiring the canonical sanitize-hook clause; `.vault/adr/2026-05-15-template-annotation-sanitization-adr.md`.
- [x] `S04` - resolve the hook config in prek order, adding .pre-commit-config.yml, across scaffold, boundary, migrate, collector, gitignore lock subjects and uninstall; `src/vaultspec_core/core/precommit.py, prek_boundary.py, diagnosis/collectors_precommit.py, gitignore.py, uninstall.py`.
- [x] `S05` - narrow the provider guard to per-machine artifacts derived from the managed-ignore source, with unstage-only remediation; `src/vaultspec_core/core/git_artifacts.py, src/vaultspec_core/cli/root_doctor.py`.
- [x] `S06` - build the staged-document check runner: per-document checkers over passed paths, related-link resolution against a name listing, and a subset-safety test per admitted checker; `src/vaultspec_core/vaultcore/checks/staged.py (new)`.
- [x] `S02` - attribute blocking findings against each staged document's HEAD version, so only introduced errors block; `src/vaultspec_core/vaultcore/checks/staged.py`.
- [x] `S07` - add the read-only commit-gate verb running the staged runner and the provider guard in one process, with file-scoped output and no mutating hints; `src/vaultspec_core/cli/root.py and a new cli verb module`.
- [x] `S08` - make vaultspec-commit-gate the one canonical hook, retire vault-fix, spec-check and check-provider-artifacts, and extend the read-only guard to the new entry and its output; `src/vaultspec_core/core/enums.py, src/vaultspec_core/core/precommit.py, .pre-commit-config.yaml, dev/guards/test_automation_contracts.py`.
- [x] `S09` - document the gate and the CI home of corpus checks, regenerate the CLI reference, and record before and after commit timings on the core vault and the 30k corpus; `docs/, src/vaultspec_core/builtins/reference/`.
- [x] `S10` - enroll the hook retirement as the 0.2.5 schema migration, converging YAML configs that carry vaultspec hooks and existing managed prek.toml blocks, never touching declined or hook-free configs; `src/vaultspec_core/migrations/m_0_2_5_commit_gate.py (new), src/vaultspec_core/migrations/__init__.py, src/vaultspec_core/core/prek_boundary.py`.
- [x] `S11` - surface duplicate vaultspec hook listings: warn on copies in configs prek does not read, and report as an error and repair the gate listed more than once in the config prek reads; `src/vaultspec_core/core/diagnosis/collectors_precommit.py, core/prek_boundary.py, core/precommit.py, core/provider_sync.py, cli/spec_cmd_doctor.py`.
- [x] `S12` - reword the builtin system clauses that told agents to learn conventions from, and gate commits on, a commit hook the gate no longer runs linters in, and re-seed core's deployed copies; `src/vaultspec_core/builtins/system/01-core.md, src/vaultspec_core/builtins/system/02-operations.md, .vaultspec/system/`.
- [x] `S13` - reword doctor's uninstalled-hook advice to offer the hook instead of ordering an install, so a repository that runs its checks explicitly is not told it is broken; `src/vaultspec_core/cli/spec_cmd_doctor.py`.

## Parallelization

Run sequentially in one worktree. S03, S01, S04 and S05 are independent of each other and of the gate, but they share `precommit.py`, the opt-out test module and the commit stream with later Steps, so parallel workers would contend for the same files. S02 extends S06, S07 wraps both, and S08 depends on S07's verb existing.

## Verification

- Each Step runs ruff check, ruff format --check, ty and its covering tests before committing, with each exit code captured separately.
- New guard tests are shown to fail with the change disabled, then pass.
- S03: a fresh `just init` run leaves no pre-commit file in the git hooks directory and reports why no hook is installed.
- S04: scaffold, migrate (including `--remove-yaml`), the doctor collector including `DECLINED_LEFTOVER`, the gitignore lock subjects and uninstall each resolve `.pre-commit-config.yml` in a temp workspace. None creates a `.yaml` next to an existing `.yml`.
- S05: in an installed consumer workspace, staged `CLAUDE.md` and `.claude/rules/*.md` pass, and a staged install manifest or lock sentinel fails with unstage-only advice.
- S06 and S02: every admitted checker has a subset test matching its whole-corpus result for the staged documents. An inherited error does not block; an introduced one does; a new document's errors block.
- S07 and S08: the gate's failure output contains no `repair`, `--fix` or `sanitize`. Sync and migrate converge a workspace carrying the three retired ids onto the single new id. Uninstall strips old and new ids.
- S09: recorded wall time per markdown commit on the core vault and on the 30k synthetic corpus, against the baseline in `2026-09-23-commit-gate-research`. The target is well under a second of gate work at 30k.
- The plan is complete when every Step is closed and the plan-close review passes. L1 has no Phase-close gate.
