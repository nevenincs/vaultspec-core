---
tags:
  - '#plan'
  - '#reference-publication-contract'
date: '2026-09-09'
tier: L2
related:
  - '[[2026-09-09-reference-publication-contract-adr]]'
modified: '2026-09-09'
body_schema: body-v2
body_hash: 'sha256:6551365c1a61bbaa454ab64befddf124c8f6307adf9d0896228c3cda0d3beee6'
---

# `reference-publication-contract` plan

Give the generated CLI and MCP references a provenance contract: capture the published
surface, render the unreleased difference, and check the published artifact against it.

## Description

Approved 2026-09-09

Authorized to work issue 519 in the dedicated `fix/519-refcontact` worktree, with the
instruction to tackle the issue and open a pull request for it. That directive is the
authorization basis for this plan's scope; the pull request is the review surface.

The work is governed by the `reference-publication-contract` decision, which settles what
a generated reference may claim about the surface it describes and where that claim is
established and checked. It narrows rather than replaces the `cli-reference-automation`
decision: the `command-inventory` region and its rendering are untouched, because the MCP
gateway's verb catalog parses that block. Grounding is the
`reference-publication-contract` reference, which records the generator's registries, the
enforcement points, the hand-written correction layer at `docs/CLI.md`, and what the three
release workflows do and do not touch.

Four deliverables, one per Phase: the published-surface snapshot and its owning verb; the
generated unreleased-surface region that retires the hand-written caveat; the MCP tool
inventory brought under the same generator; and the release-lane wiring that refreshes the
snapshot on the candidate branch and verifies it against the published distribution.

## Steps

### Phase `P01` - capture the published surface

A machine-written snapshot records the verb paths and MCP tool names of the published release, written only by its owning verb.

- [x] `P01.S01` - Model the published surface as a serializable record of version, CLI verb paths, and MCP tool names, collected from the live Typer tree and the MCP tool registry; `src/vaultspec_core/cli/reference_gen.py`.
- [x] `P01.S02` - Add the owning verb that writes and verifies the snapshot, and commit the snapshot for the current published release; `src/vaultspec_core/cli/spec_cmd_reference.py, src/vaultspec_core/builtins/reference/published-surface.json`.
- [x] `P01.S03` - Cover the snapshot model and verb with tests for capture, idempotent rewrite, and check-mode mismatch; `src/vaultspec_core/tests/cli/`.

### Phase `P02` - render the unreleased difference

A generated region states which verbs and tools exist on HEAD and not in the published release, replacing the hand-written caveat.

- [ ] `P02.S04` - Render the unreleased-surface region from the difference between the live surface and the snapshot, with an explicit empty state; `src/vaultspec_core/cli/reference_gen.py`.
- [ ] `P02.S05` - Add the region markers to both CLI surfaces and delete the hand-written release caveat; `src/vaultspec_core/builtins/reference/cli.md, docs/CLI.md`.
- [ ] `P02.S06` - Guard that attribution is generated rather than authored and that no version caveat can expire; `dev/guards/`.

### Phase `P03` - bring the MCP reference under the generator

The MCP tool inventory becomes a managed region on the same marker grammar and registry as the CLI surface.

- [ ] `P03.S07` - Render the MCP tool inventory from the server tool registry and register the MCP handbook in the managed-file registry; `src/vaultspec_core/cli/reference_gen.py`.
- [ ] `P03.S08` - Add the tool-inventory and unreleased-surface markers to the MCP handbook; `docs/MCP.md`.
- [ ] `P03.S09` - Cover MCP inventory rendering and drift with tests; `src/vaultspec_core/tests/cli/`.

### Phase `P04` - wire the release lane

The candidate branch refreshes the snapshot and the publish lane verifies the published distribution's surface against the snapshot committed at its tag.

- [ ] `P04.S10` - Refresh the snapshot on the release candidate branch beside the lockfile regeneration; `.github/workflows/release-please.yml`.
- [ ] `P04.S11` - Verify the published distribution's surface against the snapshot committed at its tag; `.github/workflows/publish.yml`.
- [ ] `P04.S12` - Guard the release-lane shape so the refresh and verification steps cannot be removed silently; `dev/guards/`.

## Parallelization

`P01` is a hard prerequisite for `P02`, `P03`, and `P04`: all three consume the snapshot
model and its owning verb. `P02` and `P03` touch disjoint files after `P01` lands and may
run concurrently. `P04` verifies against artifacts `P01` defines and is sequenced last so
the workflow changes reference a settled snapshot shape.

## Verification

- `vaultspec-core spec reference generate --check` exits zero on a clean tree and non-zero
  when either the CLI or the MCP surface drifts from its committed reference.
- The snapshot verb is idempotent: running it twice on an unchanged tree makes no second
  change and reports the unchanged outcome.
- With a snapshot naming a published version older than the live surface, the generated
  unreleased-surface region names every verb and tool present on HEAD and absent from that
  release, and no hand-written version caveat remains in `docs/CLI.md`.
- With a snapshot matching the live surface, the region renders its empty state and no
  guard turns red - a release being cut must not fail a check.
- Guards hold the release-lane shape: the candidate branch refreshes the snapshot, and the
  publish lane fails when a published distribution's surface differs from the snapshot
  committed at its tag.
- `just check-type-strict`, `ruff check`, `ruff format --check`, and
  `vaultspec-core vault check all` pass.
