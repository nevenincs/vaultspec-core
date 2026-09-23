---
tags:
  - '#adr'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:88b6a4013689b74e1f86b2d0e7dd78a68eafe36f3d3bc8a3e49098641bcb739c'
related:
  - "[[2026-09-23-commit-gate-research]]"
  - "[[2026-02-24-vault-doctor-suite-adr]]"
  - "[[2026-05-15-template-annotation-sanitization-adr]]"
  - "[[2026-07-30-modified-stamp-provenance-adr]]"
  - "[[2026-05-17-cli-spec-gitignore-adr]]"
  - "[[2026-07-23-prek-boundary-hardening-adr]]"
---

# `commit-gate` adr: `the commit gate checks what the commit stages, in one process` | (**status:** `accepted`)

## Problem Statement

The canonical commit hooks are meant to be an extra safety net that keeps vault quality
up without slowing anyone down. As shipped, they do the opposite at scale. Every markdown
commit rebuilds and checks the whole vault in three interpreter processes. That costs time
linear in vault size, blocks the author on findings and workspace state their commit did
not introduce, and ends a failure by recommending vault-wide mutation. The provider guard
also blocks files the sharing policy says to commit. `2026-09-23-commit-gate-research`
records the measurements and code evidence. Consumers get this hook set scaffolded by
default, so the shape of the gate is a public interface: changing it rewrites their hook
configuration, and that needs a decision before any code moves.

## Considerations

- Commit time must stay within a few seconds at any vault size (user constraint); the
  shipped set costs about 3.9s at 1k and about 29s at 30k documents
  (`2026-09-23-commit-gate-research`, cost finding).
- prek stashes unstaged work for the whole hook run, so hook duration is also the window
  for losing concurrent edits (`2026-09-23-commit-gate-research`, cost finding).
- A gate must never mutate the tree and never propose a mutating action
  (`2026-07-30-modified-stamp-provenance-adr`; `src/vaultspec_core/core/precommit.py:108-118`).
- A gate blocks only on defects the commit introduces; advisory and workspace-health
  conditions never block (user constraint).
- The staged-file hook was already decided in `2026-02-24-vault-doctor-suite-adr` and the
  implementation drifted from it.
- Team-shared provider projections are committed by policy
  (`2026-05-17-cli-spec-gitignore-adr`).
- Existing installs carry the old hook ids in `.pre-commit-config.yaml` or a managed
  `prek.toml` block, and must converge without hand edits (`2026-07-23-prek-boundary-hardening-adr`;
  retirement mechanism from commit `981a0c02`).
- Core's merge gate already runs the whole-corpus check (`.github/workflows/merge-gate.yml:208`,
  `just vault-check`).

## Considered options

- **Keep the three hooks.** Rejected: fails the time constraint beyond about 1k documents,
  and keeps non-attributable blocking and destructive advice.
- **One process, current semantics** (whole-vault check, doctor and provider guard in one
  interpreter). Rejected: saves only about 0.8s of startup, stays linear (about 25s at
  30k), and still blocks on workspace state and other authors' findings.
- **Incremental graph cache under the current hooks.** Rejected: keeps corpus semantics but
  still stats every file and runs every checker, about 3s at 10k, for a large engineering
  cost.
- **Staged-document gate in one process; corpus integrity in CI and explicit runs.**
  Chosen.

## Constraints

- The gate reads staged content from the working tree. That holds because prek stashes
  unstaged changes before hooks run (relayed prek 0.5.3 behaviour, not re-verified; see
  `2026-09-23-commit-gate-research`). A manual run with `--files` or `--all-files` checks
  the working tree as it stands, which is the intended meaning of those flags.
- Per-document checkers take a `VaultSnapshot` mapping and a single document parses
  through `parse_vault_metadata`. Both are stable internal interfaces
  (`src/vaultspec_core/graph/api.py:871-900`, `src/vaultspec_core/vaultcore/parser.py:211`).
- Whether `exec_mapping` and `modified_stamp` keep their meaning on a subset is unverified.
  The implementation must establish it per checker, and keep a checker out of the gate
  rather than weaken it.

## Implementation

**One canonical hook.** A single hook id, `vaultspec-commit-gate`, replaces `vault-fix`,
`spec-check` and `check-provider-artifacts`. It runs one new read-only verb in one
interpreter, with `pass_filenames: true` and `always_run: true`, so it sees every staged
path on every commit and is never skipped. The rendered entry keeps the mode-aware prefix
(`uv run --no-sync` or `uvx --from`).

**What it checks.** Staged paths under `.vault/` ending in `.md` get the document-scoped
checkers: naming and structure of that file, frontmatter, annotations, markdown hygiene,
link form, body links, placeholders, ADR status, body sections, encoding, and the stamp
and ledger checkers where they prove subset-safe. Their `related:` links resolve against a
listing of vault document names, so broken links from staged documents are caught without
a corpus parse. Every staged path goes through the provider guard. Nothing else runs at
commit time: no graph build, no doctor, no corpus properties (orphans, feature coverage and
indexes, research-to-ADR references, ADR grounding by type, rename integrity, foreign
files).

**When it blocks.** Only on an error-level finding in a staged document that the same
document's HEAD version does not already have. A new document has no HEAD version, so all
its errors count. The HEAD version is read per document from the object database, never
by building a ref-scoped corpus. Warnings, inherited errors, and every other observation
print as advisory and the gate exits 0.

**Provider guard.** It blocks only per-machine artifacts. The pattern set is derived from
the same source as the managed `.gitignore` block (lock sentinels, the install manifest,
snapshots, provider session caches), so the two cannot drift. Team-shared projections
(`CLAUDE.md`, `.mcp.json`, provider rule, skill and agent directories) pass. The
remediation it prints is to unstage, never to untrack.

**Output.** The gate prints each finding with its file and, where one exists, a fix scoped
to that file. It never prints `vault repair`, a vault-wide `--fix`, a sanitize verb, or
next-step hints. The read-only guard test from commit `981a0c02` extends to the new entry
and its failure output.

**Corpus integrity stays enforced elsewhere.** `vault check all` remains the whole-corpus
gate for CI and explicit runs, and `spec doctor` remains the workspace-health command.
Neither runs at commit time.

**Convergence.** `vault-fix`, `spec-check` and `check-provider-artifacts` join
`RETIRED_HOOK_IDS`. Sync removes them from a managed `.pre-commit-config.yaml` and adds the
new id. `spec precommit migrate` re-renders a managed `prek.toml` block that still carries
them. Uninstall strips both old and new ids. Hook-config resolution follows prek's order
(`prek.toml`, then `.pre-commit-config.yaml`, then `.pre-commit-config.yml`), so a
workspace on the `.yml` spelling is managed in place rather than given a second config.

The retirement also ships as a versioned schema migration targeting the 0.2.5 release. The
registry's explicit triggers (`install --upgrade`, `migrations run`, `vault repair`)
therefore converge every existing install once, and `migrations status` reports it as
pending until they do. The migration converges a YAML config only while it still carries
vaultspec hooks, including one whose install stopped managing it. It refreshes only an
existing managed `prek.toml` block, never adds one, and leaves a declined workspace
untouched (amended 2026-09-23 on the user's instruction to enroll the hook changes in the
per-release schema migrations).

**Duplicate listings.** A copy of vaultspec's hooks in a config prek does not read (a
`.pre-commit-config.yml` behind a `.pre-commit-config.yaml`, or any YAML behind `prek.toml`)
never runs. Doctor reports it as a warning naming the unread file, and nothing repairs it,
because the file is the operator's. The config prek does read listing a canonical hook more
than once runs it repeatedly on every commit. That covers the gate twice in one YAML, two
managed blocks in `prek.toml`, and a managed block beside a hand-written copy. Doctor reports
it as an error, and `sync`, `spec precommit migrate` and the 0.2.5 migration repair it:

- a YAML config keeps its first entry of each canonical hook, across every local repo;
- `prek.toml` keeps one managed block, or none when the operator's own copy stands, since
  vaultspec never edits outside its markers.

The repairs log what they removed. The commit gate itself reports neither condition (amended
2026-09-23 after the user asked that duplicates be surfaced this way. Their answer to the
design question did not arrive, so the recommended option was implemented and awaits their
confirmation).

**Revision of prior decisions.** This record realizes the pre-commit section of
`2026-02-24-vault-doctor-suite-adr`: staged files passed by the runner, error-only
blocking, and the deeper link and chain checks outside the commit path. It narrows
blocking to errors the commit introduces. It also revises
`2026-05-15-template-annotation-sanitization-adr`: annotations are reported, and the
canonical `vault sanitize annotations` hook stays retired. That clause's amendment is
applied to that record once this one is accepted.

## Rationale

The time constraint knocks out every whole-corpus option: their cost grows with the vault,
and the fastest of them still misses the budget at 10k documents. The staged-document
gate's cost grows with the commit; it prototypes at about 0.3s in-process at 30k
(`2026-09-23-commit-gate-research`, feasibility finding). The same scoping makes blocking
attributable: the author answers only for what they staged, and inherited findings stay
visible without holding anyone hostage. Corpus properties are real, but they are about the
vault, not about one commit, and CI already checks them where time is free. Doctor's
blocking signals are machine and workspace state, which the author cannot fix by editing
the commit. The provider guard's current patterns contradict an accepted sharing decision.
One process and one hook id also shorten the stash window and simplify convergence.

## Consequences

- Markdown commits cost about the interpreter startup plus a name listing, independent of
  vault size, and the stash window shrinks to match.
- A commit can land while the vault has corpus-level findings elsewhere. CI and
  `vault check all` catch them, and an author's own documents stay clean. Teams that relied
  on the hook as their only vault check now need CI or an explicit run; scaffolding
  guidance must say so.
- Cross-document effects of a staged change are not judged at commit time. Deleting or
  renaming a document that others link to shows up in CI, not in the hook. The gate can
  report them as advisory when the staged set includes deletions or renames.
- Consumer hook configs change on their next sync. Workspaces that customised the old
  entries in operator-owned `prek.toml` content keep them until the operator acts; migrate
  only rewrites the managed block.
- The gate needs its own subset tests per checker. A checker that cannot be made
  subset-safe stays in `vault check all` only.
- Doctor is no longer forced to stay commit-fast, which frees it to grow deeper diagnosis.
