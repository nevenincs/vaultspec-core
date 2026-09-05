---
tags:
  - '#audit'
  - '#install-degraded-robustness'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:8968b12a6426dc6d7655c7b3e698376e1ea0e0871f261c49139f006fc056272c'
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

`collect_gitignore_state` maps an `OSError` on read to `NO_FILE`, which after this work is the informational reading reserved for a workspace that never asked for management. An installed workspace whose ignore file cannot be read - a permission bit, a lock held by another process - therefore reports `gitignore info no_file` and exits `0`, which is the same shape as the defect this work closed. The collector logs a warning first, so the condition is observable in the log and nowhere in the report. Repaired in `P07` after this audit named it: an unreadable or undecodable ignore file in an installed workspace now reads as `UNMANAGED`, and the collector's own failure fallback degrades the same way rather than reporting a clean absence. The undecodable case was worse than the permission case this finding described - `read_text` raises `UnicodeDecodeError`, which the collector did not catch at all, so the failure escaped to the outer handler and landed on the same benign reading by a second route.

### opt-out-inference-window | medium | A deleted block is unrecorded until the next sync

The opt-out is recorded by `_reconcile_gitignore_opt_out`, which runs on sync. Between deleting the block and the next sync, an installed workspace reads as `UNMANAGED` and `doctor` weighs it - correctly, since nothing yet distinguishes a decision from an accident, but it means the reader sees a warning they cannot clear except by running sync or restoring the block. `P06` narrowed this from "any sync but the one you probably ran" to "any sync"; it does not remove the window. The alternative - a first-class `vaultspec-core spec gitignore disable` verb mirroring the pre-commit opt-out - was not evaluated.

### upgrade-writes-a-file-it-did-not-before | medium | The first upgrade after this lands shows a diff

`_finalize_upgrade_manifest` now reconciles the managed block on every upgrade rather than only under `--force`. Any workspace whose block is absent or short will see `.gitignore` change on its next `install --upgrade`, which previously left the file alone. This is the intended repair path and is named in the ADR's consequences, but it is a behaviour change for every existing installation, not only the broken ones: a workspace whose block predates a policy change converges silently rather than on request.

### wider-block-on-declined-subjects | low | Inert entries appear for subjects that may never exist

Deriving the sentinel list from `managed_lock_candidates` means `/.pre-commit-config.yaml.lock` is listed in a workspace that has declined pre-commit hooks, and every root lock subject is listed before its subject exists. Each such entry is inert - git ignores a path that never appears - and the ADR accepts the cost explicitly on the asymmetry argument. Recorded so a future reader does not mistake the widening for a regression.

### plan-ids-non-monotonic | low | `vault plan check` reports PLAN022 on this plan

Three Steps (`S18`, `S19`, `S20`) and later `S21`/`S22` were appended into Phases that already had higher-numbered successors, so canonical ids are not monotonic in document order. The check names this as possibly-by-design, and here it is: each was a real Step discovered during its Phase rather than a hand-edit. No action.

### preexisting-mdformat-failures | low | `just lint` fails on three files this work did not touch

`docs/channels.md`, `docs/correctness.md` and `docs/MCP.md` fail the `mdformat --check` step at this branch's base commit `3e268c1c` and still fail. Repaired here - see `main-was-red-at-base` below.

### preexisting-cli-reference-drift | low | The generated CLI reference is out of sync at the base commit

`test_cli_reference_generated` fails three ways on `docs/CLI.md`, which this work does not touch. The differences are paragraph re-wrapping: the checked-in file is wrapped as `mdformat` leaves it and the generator wants its own fill. Both gates are live, so the file cannot satisfy them at once, and regenerating would only move the failure to the `mdformat --check` step. Present at base commit `3e268c1c`. Repaired here - see `main-was-red-at-base` below.

### preexisting-bare-command-guard | low | Three prose cross-references fail the CLI-language guard

`dev/guards/test_cli_language_contract.py::test_docs_do_not_teach_bare_cli_commands` flags `vault graph` in the CLI reference, `vault sanitize annotations` in the framework manual and `vault check` in the README. All three are prose cross-references rather than runnable snippets, and all three predate this branch. One further offender was introduced here - `install --force` in the framework manual's new opt-out paragraph - and was corrected. The guard cannot tell a cross-reference from a snippet, which is a guard-design question rather than a documentation defect; the three were given their entry point anyway, because a red gate that everyone learns to ignore is worse than a slightly wordy sentence.

### preexisting-gemini-binary-test | low | One test fails for want of a local binary

`test_agents_render.py::TestGeminiCliLoadsRenderedAgents::test_all_source_agents_load` fails on `assert gemini_bin is not None`. It is environmental - no `gemini` CLI on this machine - and unrelated to anything here. It was deselected from the full-suite run and is noted so the deselection is not mistaken for a suppression.

### main-was-red-at-base | high | Every gate this branch inherits was already failing

`main` at `3e268c1c` fails its own CI on four counts, none of them introduced here: the markdown format check on three documents, three `test_cli_reference_generated` assertions against a stale `docs/CLI.md`, and the bare-command guard. The scheduled Main CI Sentinel has been failing with them.

They were repaired on this branch rather than filed, because a fix for GH issue 399 that cannot show a green run proves nothing about itself. The repair is mechanical: `just fix markdown` followed by `vaultspec-core spec reference generate`, then the three prose cross-references given their entry point. The two formatters do converge - the earlier reading that they could not was an artefact of running plain `mdformat` without the `--wrap 88` pass the toolchain applies to those five documents, which is a trap for anyone reaching for `mdformat` directly rather than through `just`.

The finding that outlives the repair is the interval. Four gates went red on a push to `main` and stayed red, which is the condition under which a gate stops being read at all - the same failure mode as a check that never runs, arrived at from the other side.

### harness-supplied-the-precondition | high | The test factory hid the reported defect

`WorkspaceFactory.install` created a `.gitignore` before every install "so the gitignore block writer has something to append to". Every install-path test therefore exercised a precondition the product did not provide, which is why a suite this large passed while `vaultspec-core install` left a fresh workspace unprotected. Removed in `P02.S18`. This is the finding with the widest reach: it is the same shape as the defect - an instrument that reports on a workspace it has quietly repaired first - and nothing structural prevents another factory helper from doing it again.

### unreadable-read-as-a-decision | critical | An unreadable ignore file was recorded as a permanent opt-out

`has_gitignore_block` answered `False` on `OSError` and `UnicodeDecodeError`, and `_reconcile_gitignore_opt_out` read that `False` as the opt-out gesture. Every state that was not "readable file carrying exactly one block" therefore became a durable recorded decision that only `--force` undoes: an undecodable file, a file the process cannot open, a directory named `.gitignore`. Reproduced by writing undecodable bytes and running `sync`, which exited `0` and left `gitignore_opted_out: true`.

The consequence is the reason this is the most serious finding in the set. A recorded opt-out makes `_management_expected` false, so the diagnosis returns to the informational reading - the exact silence `P04` and `P07` removed, restored through the writer rather than the reader, and made permanent. The two repairs were each correct and the pair was not.

Fixed by `managed_block_presence`, a three-state predicate: `True` and `False` are observations, `None` means the question could not be answered. Both reconcilers stand down on `None` and leave the flags where they are. The boolean predicates survive as thin wrappers for the callers that genuinely want leniency.

### uninstall-provisioned-what-it-should-only-remove | high | A partial uninstall recreated a deleted ignore file

`_reconcile_uninstall_git_blocks` called `ensure_gitignore_block` with no gate beyond "was managed before". That was harmless while the writer skipped an absent file, and became a defect the moment it created one: `uninstall <provider> --force` against a workspace that had deleted its `.gitignore` wrote the file back, with the full block, before any sync could read that deletion as the opt-out gesture. It also contradicted this feature's own ADR, which mitigates unconditional creation by scoping it to install and upgrade.

Gated on the file existing and on no recorded opt-out. Uninstall removes; it does not provision.

### degraded-condition-sweep | high | Sixteen further gaps of the same shape remain open

A systematic sweep of every entry point against every degraded condition - absent, empty, unreadable, undecodable, read-only, directory-where-a-file-belongs, symlink, no `.git`, partially scaffolded, corrupt manifest, legacy manifest, concurrent runs, dry-run leakage, swallowed exceptions - returned sixteen further findings beyond the two above. All reproduced except where marked. They are listed here so the sweep is not lost; none is claimed as in scope for this feature.

| Slug                                           | Severity | Summary                                                                                                                                                                                      |
| ---------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `legacy-manifest-skips-migrations`             | high     | A v1.0 manifest reads as "not installed", so every migration is skipped; the upgrade then stamps the running version and certifies all nine as applied                                       |
| `corrupt-workspace-json-doctor-ok`             | high     | A declaration every mutating verb refuses is reported healthy, exit `0`, with two false `ok` rows                                                                                            |
| `unparseable-precommit-yaml-reads-as-absent`   | high     | Upgrade exits `0`, management stands down, the diagnosis says `info`                                                                                                                         |
| `uninstall-leaves-unignored-sentinels`         | high     | Three lock sentinels left untracked and unignored; the `.gitattributes` block survives a full uninstall                                                                                      |
| `undecodable-gitattributes`                    | medium   | The gitattributes twin: `info no_file` in the diagnosis, raw traceback from `install --force`. The sync half is closed by `managed_block_presence`; the read and write halves are not        |
| `gitattributes-never-reconciled-on-upgrade`    | medium   | R3 for `.gitattributes` - the upgrade path never calls its writer at all                                                                                                                     |
| `manifest-repair-drops-management-flags`       | medium   | Preflight rebuilds the manifest from defaults, so every `*_managed` flag clears and sync stops managing every root file                                                                      |
| `corrupt-mcp-json-doctor-info`                 | medium   | A file that fails every sync is unweighed in the diagnosis                                                                                                                                   |
| `atomic-write-fchmod-leak-masks-error`         | medium   | A read-only destination on Windows leaks the temp file and surfaces an error naming the temp, with the real cause only in `__context__`                                                      |
| `symlinked-gitignore-severed`                  | medium   | The block write replaces a symlink with a regular file; the real target is left stale and the run exits `0`                                                                                  |
| `undecodable-precommit-yaml-traceback`         | medium   | `UnicodeDecodeError` sits outside the `(YAMLError, OSError)` net in both the scaffold and the collector                                                                                      |
| `install-swallows-sync-failure`                | medium   | A failing provider sync is caught into `result["errors"]`, which neither renderer reads. Unverified - a reading of the render path, not a measurement                                        |
| `vault-dir-not-restored-and-block-shrinks`     | low      | With `.vault/` deleted, upgrade does not re-scaffold it and the block silently loses its four `.vault/` entries                                                                              |
| `failed-install-force-leaves-partial-manifest` | low      | Providers recorded before a mid-run failure, final manifest write never reached; the retry then refuses as already installed                                                                 |
| `sync-early-exit-discards-errors`              | low      | `cmd_sync` returns before the failure code is computed when no providers are enrolled. Unverified                                                                                            |
| `unlocked-manifest-rmw`                        | low      | Five read-modify-write cycles write the manifest without the lock its own docstring requires. Unverified - the window exists by construction, three concurrent rounds produced no corruption |

Five of these - `corrupt-workspace-json-doctor-ok`, `unparseable-precommit-yaml-reads-as-absent`, `undecodable-gitattributes`, `corrupt-mcp-json-doctor-info`, `undecodable-precommit-yaml-traceback` - are one defect wearing five hats: every `_safe_*` wrapper in `diagnosis.py` maps "could not read or parse" onto the neutral signal. That is the instrument pattern at the layer above the collectors, and it is what let `unreadable-read-as-a-decision` and `manifest-repair-drops-management-flags` hide as well.

## Recommendations

- Evaluate a first-class opt-out verb for the managed blocks, mirroring `spec precommit disable`, which would record the decision at the moment it is made instead of inferring it on the next sync. This is architecturally significant: a follow-on ADR must decide whether declining a managed block is a per-machine state in the manifest, as it is today, or a committed workspace declaration alongside `hooks.pre_commit`, which would make it travel to teammates.
- Introduce one explicit "could not read" signal across the diagnosis and weigh it, replacing the `_safe_*` fallbacks that map a failed collector onto the neutral value. One structural change closes five of the sixteen findings above and removes the layer that hid two more.
- Split `UNREADABLE` out of `UNMANAGED` as part of that change: the three conditions `UNMANAGED` currently collapses call for different remediations, and the one the resolver currently offers for an undecodable file cannot run.
- Teach `list_pending` to distinguish "no manifest" from "a manifest with no version", so a workspace written before migrations existed stops being certified as fully migrated.
- Audit the remaining `WorkspaceFactory` helpers for other preconditions the harness supplies that the product does not, and state in the factory's docstring that seeding a managed artefact before the verb under test writes it is the one thing it must not do.
- Give `main` a red-CI alarm that reaches someone. The Sentinel workflow already runs and already reports failure; what is missing is the consequence. Four mechanical failures survived a push and a scheduled run without being repaired.
- Decide whether the unconditional upgrade reconciliation should announce itself. It repairs silently today; a one-line advisory naming the file it changed would make the first upgrade after this release explicable to a reader who did not ask for it.
