---
tags:
  - '#audit'
  - '#install-degraded-robustness'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:ff540b3a39326c37a8e60928a24593eb97bcd13e9048e6cd6bd014e0b09f3b5e'
related:
  - "[[2026-09-04-install-degraded-robustness-plan]]"
  - "[[2026-09-04-install-degraded-robustness-adr]]"
---

# `install-degraded-robustness` audit: `Provisioning robustness on degraded workspaces, post-implementation`

## Scope

The six Phases of `2026-09-04-install-degraded-robustness-plan`, as landed on `fix/399-gitignore`: the sentinel derivation, the ignore-block write path, upgrade reconvergence, the diagnosis and its exit code, the authored documentation, and the sync opt-out reconciliation. Audited against the decision in `2026-09-04-install-degraded-robustness-adr` and the four defects grounded in `2026-09-04-install-degraded-robustness-research`, plus the reproductions run on a real filesystem with a real `git`.

What this audit covers is the residue: behaviour that changed as a side effect, conditions the new checks still cannot see, and findings surfaced during implementation that were deliberately not acted on. The four reported defects are closed and verified; they are not re-argued here.

## Findings

### unreadable-ignore-file | medium | An unreadable `.gitignore` still reads as benign

`collect_gitignore_state` maps an `OSError` on read to `NO_FILE`, which after this work is the informational reading reserved for a workspace that never asked for management. An installed workspace whose ignore file cannot be read - a permission bit, a lock held by another process - therefore reports `gitignore info no_file` and exits `0`, which is the same shape as the defect this work closed. The collector logs a warning first, so the condition is observable in the log and nowhere in the report. Not touched here because it was outside the plan's Phases and no reproduction was run against it.

### opt-out-inference-window | medium | A deleted block is unrecorded until the next sync

The opt-out is recorded by `_reconcile_gitignore_opt_out`, which runs on sync. Between deleting the block and the next sync, an installed workspace reads as `UNMANAGED` and `doctor` weighs it - correctly, since nothing yet distinguishes a decision from an accident, but it means the reader sees a warning they cannot clear except by running sync or restoring the block. `P06` narrowed this from "any sync but the one you probably ran" to "any sync"; it does not remove the window. The alternative - a first-class `vaultspec-core spec gitignore disable` verb mirroring the pre-commit opt-out - was not evaluated.

### upgrade-writes-a-file-it-did-not-before | medium | The first upgrade after this lands shows a diff

`_finalize_upgrade_manifest` now reconciles the managed block on every upgrade rather than only under `--force`. Any workspace whose block is absent or short will see `.gitignore` change on its next `install --upgrade`, which previously left the file alone. This is the intended repair path and is named in the ADR's consequences, but it is a behaviour change for every existing installation, not only the broken ones: a workspace whose block predates a policy change converges silently rather than on request.

### wider-block-on-declined-subjects | low | Inert entries appear for subjects that may never exist

Deriving the sentinel list from `managed_lock_candidates` means `/.pre-commit-config.yaml.lock` is listed in a workspace that has declined pre-commit hooks, and every root lock subject is listed before its subject exists. Each such entry is inert - git ignores a path that never appears - and the ADR accepts the cost explicitly on the asymmetry argument. Recorded so a future reader does not mistake the widening for a regression.

### plan-ids-non-monotonic | low | `vault plan check` reports PLAN022 on this plan

Three Steps (`S18`, `S19`, `S20`) and later `S21`/`S22` were appended into Phases that already had higher-numbered successors, so canonical ids are not monotonic in document order. The check names this as possibly-by-design, and here it is: each was a real Step discovered during its Phase rather than a hand-edit. No action.

### preexisting-mdformat-failures | low | `just lint` fails on three files this work did not touch

`docs/channels.md`, `docs/correctness.md` and `docs/MCP.md` fail the `mdformat --check` step at this branch's base commit `3e268c1c` and still fail. They were left alone rather than reformatted, because a formatting sweep of unrelated documentation does not belong in this change. The lint lane therefore does not pass end to end on this branch; `just lint type` does, and every file this work touched is formatted.

### preexisting-cli-reference-drift | low | The generated CLI reference is out of sync at the base commit

`test_cli_reference_generated` fails three ways on `docs/CLI.md`, which this work does not touch. The differences are paragraph re-wrapping: the checked-in file is wrapped as `mdformat` leaves it and the generator wants its own fill. Both gates are live, so the file cannot satisfy them at once, and regenerating would only move the failure to the `mdformat --check` step. Present at base commit `3e268c1c`; left alone.

### preexisting-bare-command-guard | low | Three prose cross-references fail the CLI-language guard

`dev/guards/test_cli_language_contract.py::test_docs_do_not_teach_bare_cli_commands` flags `vault graph` in the CLI reference, `vault sanitize annotations` in the framework manual and `vault check` in the README. All three are prose cross-references rather than runnable snippets, and all three predate this branch. One further offender was introduced here - `install --force` in the framework manual's new opt-out paragraph - and was corrected. The guard's inability to tell a cross-reference from a snippet is a guard-design question, not a documentation defect.

### preexisting-gemini-binary-test | low | One test fails for want of a local binary

`test_agents_render.py::TestGeminiCliLoadsRenderedAgents::test_all_source_agents_load` fails on `assert gemini_bin is not None`. It is environmental - no `gemini` CLI on this machine - and unrelated to anything here. It was deselected from the full-suite run and is noted so the deselection is not mistaken for a suppression.

### harness-supplied-the-precondition | high | The test factory hid the reported defect

`WorkspaceFactory.install` created a `.gitignore` before every install "so the gitignore block writer has something to append to". Every install-path test therefore exercised a precondition the product did not provide, which is why a suite this large passed while `vaultspec-core install` left a fresh workspace unprotected. Removed in `P02.S18`. This is the finding with the widest reach: it is the same shape as the defect - an instrument that reports on a workspace it has quietly repaired first - and nothing structural prevents another factory helper from doing it again.

## Recommendations

- Map an unreadable `.gitignore` in an installed workspace onto a weighed signal rather than onto `NO_FILE`, so the benign reading means only what it says. Small enough to land without a decision record.
- Evaluate a first-class opt-out verb for the managed blocks, mirroring `spec precommit disable`, which would record the decision at the moment it is made instead of inferring it on the next sync. This is architecturally significant: a follow-on ADR must decide whether declining a managed block is a per-machine state in the manifest, as it is today, or a committed workspace declaration alongside `hooks.pre_commit`, which would make it travel to teammates.
- Audit the remaining `WorkspaceFactory` helpers for other preconditions the harness supplies that the product does not, and state in the factory's docstring that seeding a managed artefact before the verb under test writes it is the one thing it must not do.
- Reconcile the two formatters that both claim `docs/CLI.md`, so its generation check and the repository's `mdformat` gate can pass together. Until then the repo lane cannot be green and neither failure carries information.
- Decide whether the unconditional upgrade reconciliation should announce itself. It repairs silently today; a one-line advisory naming the file it changed would make the first upgrade after this release explicable to a reader who did not ask for it.
