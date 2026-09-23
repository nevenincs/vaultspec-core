---
tags:
  - '#adr'
  - '#commit-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:c05991958845cd6748313297ad2e7faaf88ac3a93c443a25b29d1e35b3c935fb'
related:
  - "[[2026-09-23-commit-gate-adr]]"
  - "[[2026-09-23-commit-gate-research]]"
---

# `commit-gate` adr: `duplicate commit-hook listings: warn when unread, error and repair when live` | (**status:** `proposed`)

## Problem Statement

Doctor, sync and the migration matched vaultspec's hook ids as a set, so a second copy of the
gate was invisible to them. Two different mistakes looked alike on disk and were both reported
as healthy:

- a copy in a config prek does not read, which never runs;
- the config prek does read listing the gate more than once, which runs it repeatedly on
  every commit.

The user asked that the first be surfaced as an advisory warning, and the second as an error
that the product fixes and reports. That changes doctor's exit-code contract and what the
repair verbs write, so it needs a decision.

## Considerations

- prek reads `prek.toml`, then `.pre-commit-config.yaml`, then `.pre-commit-config.yml`, and
  runs only the first it finds (`2026-09-23-commit-gate-research`, config resolution
  finding).
- vaultspec never edits `prek.toml` outside its own markers
  (`2026-07-23-prek-boundary-hardening-adr`).
- A gate must never block commits on advisory conditions (`2026-09-23-commit-gate-adr`).
  Doctor is not a commit hook, so an error there fails CI health checks, not commits.
- An error the product claims to fix and cannot fix is worse than no report at all.

## Considered options

- **Report nothing** (the previous behaviour). Rejected: a doubled gate costs every commit,
  and a shadowed copy misleads anyone who reads the file.
- **Error for every duplicate, and delete shadowed copies.** Rejected: a shadowed file is the
  operator's, and deleting from it without being asked is exactly the destructive repair
  this work removed.
- **Report both, repair neither.** Rejected: a duplicated managed block or scaffolded entry is
  vaultspec's own content, and leaving it for the operator shifts vaultspec's mistake onto
  them.
- **Warn on shadowed copies, report live duplicates as an error and repair what vaultspec
  owns.** Chosen, pending acceptance.

## Constraints

- Signal priority: a fault in the live config outranks a shadowed copy, and a declined
  workspace outranks both.
- Repairs are confined to vaultspec's own entries: YAML hook mappings with a canonical id, and
  lines between the `prek.toml` markers.

## Implementation

A copy of vaultspec's hooks (current or retired) in a config prek does not read is doctor's
`SHADOWED` signal. It is a warning that names the unread file, and nothing repairs it.

The config prek reads listing a canonical hook more than once is doctor's `DUPLICATED` signal,
and it is an error. `sync`, `spec precommit migrate` and the 0.2.5 migration repair it:

- a YAML config keeps its first entry of each canonical hook, across every local repo, and
  drops any local repo the repair itself emptied;
- `prek.toml` keeps one managed block, or none when the operator's own copy stands.

Each repair logs what it removed. When the only duplicates lie outside vaultspec's markers,
nothing is repaired, and every surface says why:

- doctor names them as the operator's to remove;
- `spec precommit migrate` reports `conflicting` and exits 1;
- `sync` warns.

The commit gate reports neither condition.

## Rationale

A doubled gate is a live cost on every commit and belongs with the errors a CI health check
fails on. A shadowed copy costs nothing at run time but misleads, which is what a warning is
for. Repairing vaultspec's own duplicates keeps the product from leaving its mistakes to the
operator. Refusing to touch the operator's entries is the boundary every other hook decision
keeps.

## Consequences

- A workspace with a doubled gate now fails `spec doctor`, which CI may run with
  `--gate-errors`, until `sync` or `migrate` repairs it. A duplicate the operator wrote needs
  a hand edit.
- A workspace carrying both hook-config spellings now warns until the unread one is removed.
- The implementation shipped in commit `be8e7f7b` and its follow-up fixes before this record
  was accepted. If it is rejected, the signals and repairs are withdrawn.
