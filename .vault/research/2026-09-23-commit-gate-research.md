---
tags:
  - '#research'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:cc76d3af1e81318bdd5df9ae4591fe8b3da23ccfa4395685c767d4318ca2e3a9'
related:
  - "[[2026-02-24-vault-doctor-suite-adr]]"
  - "[[2026-05-15-template-annotation-sanitization-adr]]"
  - "[[2026-07-30-modified-stamp-provenance-adr]]"
  - "[[2026-05-17-cli-spec-gitignore-adr]]"
  - "[[2026-07-23-prek-boundary-hardening-adr]]"
---

# `commit-gate` research: `scoping the commit gate to what a commit changes`

Question: what should the canonical commit hook check, and over what scope, so it stays
within a few seconds at any vault size, blocks only on defects the commit introduces, and
never proposes a mutating action? It matters because every markdown commit in every
consumer pays for the gate, and prek stashes the author's unstaged work for as long as it
runs. The evidence says the shipped gate runs whole-corpus with no commit scoping, costs
time linear in vault size (about 29s per commit at 30k documents), and blocks on workspace
state and pre-existing findings. A staged-document gate prototypes at 0.3s in-process at
30k. The staged-file design already exists in an accepted decision the implementation
drifted from. What the ADR must settle: the gate's scope and blocking rule, the fate of the
doctor and provider hooks, and how existing installs converge.

## Findings

### The shipped gate never scopes to the commit

After commit `981a0c02` three canonical hooks remain, all `pass_filenames: false`
(`src/vaultspec_core/core/precommit.py:108-150`):

- `vault-fix` runs `vault check all`, filtered by `types: [markdown]`;
- `spec-check` runs `spec doctor --gate-errors`, filtered by `types: [markdown]`;
- `check-provider-artifacts` runs `check-providers` with `always_run: true`.

Only `check-providers` reads the staging area
(`src/vaultspec_core/core/git_artifacts.py:316-360`). No vault checker accepts a path set;
every signature takes a whole-corpus snapshot or graph
(`src/vaultspec_core/vaultcore/checks/__init__.py:80-147`). `types: [markdown]` also fires
the vault hooks on `README.md` and `docs/` edits that never touch `.vault/`.

### Cost is linear in vault size and dominated by the graph build

Measured on Windows 11 at commit `a04e918a`, calling the CLI directly (no uv), with
synthetic vaults from `src/vaultspec_core/testing/synthetic.py:752` padded to 5.8 KB per
document, the average of the real 863-document core vault (5.0 MB). The real vault
measures 1.61s for `vault check all` and 0.70s for doctor, matching the 1k row. "Edited"
is the normal state at commit time: one document changed since the last run.

| docs   | `vault check all` cold / warm / edited | doctor | `check-providers` | per commit, with 3 x 0.4s uv startup |
| ------ | -------------------------------------- | ------ | ----------------- | ------------------------------------ |
| 1,000  | 1.57 / 1.26 / 1.54s                    | 0.75s  | 0.42s             | ~3.9s                                |
| 5,000  | 3.89 / 2.60 / 4.32s                    | 1.16s  | 0.42s             | ~7.1s                                |
| 10,000 | 7.23 / 4.53 / 7.82s                    | 1.81s  | 0.43s             | ~11.2s                               |
| 30,000 | 21.40 / 12.85 / 22.84s                 | 4.54s  | 0.41s             | ~29s                                 |

- At 10k documents the cold graph build and snapshot take 4.24s. All 20 checkers together
  take about 3s; the largest are `foreign` (0.52s), `exec_mapping` (0.48s), `schema`
  (0.33s) and `body_sections` (0.30s).
- The graph cache is all-or-nothing: any changed, added or removed file invalidates it
  (`src/vaultspec_core/graph/cache.py:1-40`), so a commit hook almost always rebuilds. A
  fully warm run still costs 12.85s at 30k.
- The synthetic corpus does not conform to vault naming and schema rules, so these runs
  also render thousands of findings; rendering was not separated from checking. The real
  vault's agreement with the 1k row bounds that distortion at small scale only.

### Blocking is not attributable to the commit

Any error-level finding anywhere in the corpus fails every markdown commit. Error sites
include dangling `related:` links (`src/vaultspec_core/vaultcore/checks/dangling.py:79`),
an approved plan linking a non-accepted ADR
(`src/vaultspec_core/vaultcore/checks/references.py:233-237`), missing ADR grounding
(`schema`), filename-convention violations
(`src/vaultspec_core/vaultcore/checks/structure.py:121-448`) and legacy index files. Each
can be introduced by another author, or by a status change elsewhere, and still blocks
someone who never touched the document.

### The doctor hook gates machine and workspace health, not the commit

`doctor_exit_code` (`src/vaultspec_core/cli/spec_cmd_doctor.py:850-980`) returns 2, the
only code `--gate-errors` keeps, for these signals:

- the framework is missing or corrupted, or a builtin is deleted;
- a gitignore or gitattributes error, or a rename-integrity error;
- a provider directory is missing or a provider manifest entry is orphaned;
- the running version is below the committed floor.

None of these is a property of the staged change. The version-floor case blocks every
markdown commit on a machine that has not upgraded. Doctor's cost grows with the vault
because `_collect_layer1_diagnosis` always runs `collect_vault_content_state`
(`src/vaultspec_core/core/diagnosis/collectors_config.py:179-218`), which reads and strips
every document to count annotations. That signal is warning-level, so `--gate-errors`
discards it. `vault check all` already runs both the annotations and rename-integrity
checkers.

### The provider hook contradicts the sharing policy and advises data loss

`PROVIDER_ARTIFACT_PATTERNS` (`src/vaultspec_core/core/git_artifacts.py:302-313`) blocks
`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `.mcp.json` and the four provider directories. The
accepted sharing decision in `2026-05-17-cli-spec-gitignore-adr` makes exactly these
team-shared. Reproduced in an installed consumer workspace: after authoring
`.vaultspec/rules/team.md` and running `sync`, staging the projections makes the hook exit
with status 1. The failure text advises `git rm --cached <file>`
(`src/vaultspec_core/cli/root_doctor.py:36-42`), which untracks the shared files for every
teammate on their next pull. Core's own repo gitignores these paths, which hides the
conflict here.

### Gate output proposes vault-wide mutation

The `("vault.check.all", "failed")` hint (`src/vaultspec_core/cli/rendering_hints.py:47-50`)
prints `vaultspec-core vault repair`. The canonical entry does not pass `--no-hints`, so
every blocked commit ends by recommending a pipeline broader than `vault check all --fix`
(`src/vaultspec_core/cli/vault_cmd.py:900`).

### The staged-file design was decided and drifted from

`2026-02-24-vault-doctor-suite-adr` specifies the hook as the vault doctor with
`pass_filenames: true`, scoped to staged files, gated by `--severity error`, with link and
chain checks as an opt-in deeper hook. The shipped `vault-fix` entry replaced that with the
whole-corpus `vault check all`. Separately, `2026-05-15-template-annotation-sanitization-adr`
added the `vault sanitize annotations` hook that commit `981a0c02` retired under the
pure-gate rule of `2026-07-30-modified-stamp-provenance-adr`. That reversal of an accepted
clause has no decision record yet.

### A staged-document gate is feasible in a fraction of a second

- `VaultSnapshot` is a plain `path -> (metadata, body)` mapping
  (`src/vaultspec_core/graph/api.py:871-900`). Checker tests already build single-document
  snapshots (`src/vaultspec_core/vaultcore/checks/tests/test_body_links.py:88-96`).
- A single document parses through `parse_vault_metadata`
  (`src/vaultspec_core/vaultcore/parser.py:211`).
- Prototype on the 30k vault, in-process: import 0.16s, listing all 30,000 document names
  0.08s, parsing 5 staged documents 0.001s, and 11 snapshot checkers over them 0.008s
  (`structure`, `frontmatter`, `annotations`, `markdown`, `links`, `body_links`,
  `placeholders`, `adr_status`, `body_sections`, `modified_stamp`, `exec_mapping`). Total
  0.28-0.30s, against 22.8s today.
- Link targets resolve against the name listing, so dangling-link detection for the staged
  documents needs no corpus parse.
- prek always stashes unstaged changes before running hooks (reported against prek 0.5.3;
  not re-verified here). So during a hook run the working tree equals the staged content,
  and reading the passed paths from disk reads what will be committed.
- Not verified: whether each subset-run checker keeps its whole-corpus semantics.
  `exec_mapping` pairs plans with ledgers and `modified_stamp` consults a fingerprint
  ledger, so a staged plan whose ledger is unstaged may report differently.
- Corpus properties cannot be judged from a subset: orphans, feature coverage and indexes,
  research-to-ADR references, ADR grounding by type, feature-rename integrity, foreign
  files, and `.vaultspec` rename integrity.

### Blocking only on what the commit introduces is cheap per document

Reading each staged document's HEAD blob with `git show HEAD:<path>` and checking it the
same way separates new findings from inherited ones at per-document cost.
`VaultGraph.from_ref` (`src/vaultspec_core/graph/api.py:138-160`) reads the whole corpus at
a ref and is too costly for a hook. Line-level attribution was considered and set aside:
frontmatter findings belong to the document, not a line.

### Options

- **Status quo.** Fails the few-seconds constraint beyond about 1k documents.
- **One process, current semantics** (whole-vault check, doctor and providers in one
  interpreter). Saves about 0.8s of interpreter startup; still linear and still blocking
  on non-attributable state. Around 25s at 30k.
- **Incremental graph cache.** Keeps whole-corpus semantics with per-file cache entries.
  Still stats every file and runs all checkers, about 3s at 10k by the checker timings
  above. Large engineering cost for a result that still misses the constraint at scale.
- **Staged-document gate in one process, whole-corpus check in CI.** Commit-sized cost,
  attributable blocking, and corpus properties still enforced where time is free. The
  evidence favours this option.

The ADR must also settle: whether doctor leaves the commit hook entirely; the provider
guard's pattern source; hint suppression in gate context; the new hook id and how old ids
retire from YAML and `prek.toml` installs; and whether `.pre-commit-config.yml` joins the
resolved config names. prek's discovery order is `prek.toml`, then
`.pre-commit-config.yaml`, then `.pre-commit-config.yml`, first found wins (reported
against prek 0.5.3 `crates/prek-consts/src/lib.rs:13`; not re-verified here). Core
resolves only the first two.

### Hook activation in core itself

`dev init` installs the hook runner into the shared git hooks directory
(`dev/init/hooks.py:1-60`; step `hook-runner` at `dev/init/plan.py:91-96`), so every core
worktree runs the gate with prek's stash cycle. `docs/framework.md:253-255` still says
vault checks are not limited to staged files and that "annotation cleanup" modifies
documents, which describes the retired hook.

Not investigated: pre-push hooks, the CI workflow that would host the whole-corpus check,
and prek's behaviour with `--files` from a manual run.

## Sources

- `src/vaultspec_core/core/precommit.py:108-150`
- `src/vaultspec_core/core/git_artifacts.py:302-360`
- `src/vaultspec_core/vaultcore/checks/__init__.py:80-147`
- `src/vaultspec_core/vaultcore/checks/dangling.py:79`
- `src/vaultspec_core/vaultcore/checks/references.py:233-237`
- `src/vaultspec_core/vaultcore/checks/structure.py:121-448`
- `src/vaultspec_core/vaultcore/checks/tests/test_body_links.py:88-96`
- `src/vaultspec_core/vaultcore/parser.py:211`
- `src/vaultspec_core/graph/api.py:138-160`, `src/vaultspec_core/graph/api.py:871-900`
- `src/vaultspec_core/graph/cache.py:1-40`
- `src/vaultspec_core/cli/spec_cmd_doctor.py:850-980`
- `src/vaultspec_core/core/diagnosis/collectors_config.py:179-218`
- `src/vaultspec_core/cli/root_doctor.py:36-42`
- `src/vaultspec_core/cli/rendering_hints.py:47-50`
- `src/vaultspec_core/cli/vault_cmd.py:900`
- `src/vaultspec_core/testing/synthetic.py:752`
- `dev/init/hooks.py:1-60`, `dev/init/plan.py:91-96`
- `docs/framework.md:253-255`
- commits `981a0c02`, `a04e918a`
- prek 0.5.3 `crates/prek-consts/src/lib.rs:13`, `crates/prek/src/workspace.rs:270-290`
  (relayed, not re-verified)
- https://github.com/nevenincs/vaultspec-core/issues/549
- https://github.com/nevenincs/vaultspec-core/issues/550
- https://github.com/nevenincs/vaultspec-core/issues/551
- https://github.com/nevenincs/vaultspec-core/issues/552
