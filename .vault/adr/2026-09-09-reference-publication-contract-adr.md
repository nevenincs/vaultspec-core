---
tags:
  - '#adr'
  - '#reference-publication-contract'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ded5177cfe3cb08945112471d1ba863d2471fc549ae2e44ac2a417b5708bcdb7'
related:
  - "[[2026-09-09-reference-publication-contract-reference]]"
  - '[[2026-06-10-cli-reference-automation-adr]]'
---

# `reference-publication-contract` adr: `candidate-versus-published reference provenance` | (**status:** `accepted`)

## Problem Statement

The generated CLI reference describes whatever command surface the working tree happens
to have. Nothing in it says which surface that is, and the one place the question has
been answered - `docs/CLI.md:2456`, "not available in the 0.1.73 release" - was answered
by hand for two commands out of the six that need it.

The reason the omission is invisible is that main's declared version equals the latest
published version. `pyproject.toml:45` and `.release-please-manifest.json` both read
`0.1.73`, which is what PyPI serves, because release-please holds the bump to `0.2.0` in
an open pull request until the release is cut. Between two releases, therefore, every
artifact generated from main carries a version string that is true of the package
metadata and false of the surface the document describes: `vault add exec` lifecycle
behavior, `vault check foreign`, `spec hooks trust`, `migrations run --dry-run`,
`spec gitignore` and `spec gitattributes`, and the dedicated MCP `log` tool are all
present in the document and absent from the release a reader can install.

A consumer of these documents cannot separate the two by any mechanical means, so it
must maintain a correction layer by hand, one entry per command, and grow it with every
merge. That layer is also the wrong shape on its own terms: it is a caveat naming a
version, and `dev/guards/test_release_provenance.py` exists because this repository has
already been bitten once by a version-scoped claim that expired on the release-please
branch under release pressure.

Two further gaps make the problem structural rather than editorial. Nothing in the
release lane regenerates or verifies a reference: `release-please.yml` refreshes
`uv.lock` on the candidate branch and refreshes nothing else, and `publish.yml` verifies
the published distribution's provenance but never its surface. And the MCP reference is
outside the generator entirely - `docs/MCP.md` carries no managed region and no drift
guard, so the tool surface has neither generation nor attribution to inherit.

The decision this record settles is what published documentation is allowed to claim
about the surface it describes, and where in the release lane that claim is established
and checked.

## Considerations

- **The candidate branch already knows the answer.** On the release-please pull request
  the version is the candidate's and the tree is main's, so a surface captured there is
  exactly the surface that will be published under that tag. `release-please.yml` already
  checks that branch out and pushes a regenerated `uv.lock` onto it, so refreshing a
  second generated artifact in the same place is an extension of an established pattern
  rather than a new mechanism.

- **Attribution needs a surface, not a version.** Knowing that the published version is
  `0.1.73` does not tell a reader which of the document's commands that release contains.
  Answering that mechanically requires a record of what the published surface *was*, to
  diff the live surface against. That record must be immutable and offline: deriving it
  from git tags at generation time would work in a full checkout and fail in the shallow,
  tagless clones CI produces, and it would give the post-publication check nothing fixed
  to verify against.

- **The correction layer is derivable once the snapshot exists.** With a committed record
  of the published surface, the set of verbs and tools that exist on HEAD and not in the
  release is a set difference. Rendering that difference into a managed region replaces
  every hand-written per-command caveat with generated content, and the region empties
  itself the moment a release ships - it cannot expire, because it is recomputed rather
  than asserted.

- **Verification after publication is a different claim from generation before it.**
  Generating from the candidate says the document matched the source at build time.
  Only reading the published artifact back proves the document matches what users can
  install. `publish.yml` already installs the built wheel in isolation for its smoke test
  and already verifies the attached assets against an immutable tag, so the shape for
  checking a released artifact exists and is proven in that lane.

- **The MCP surface is enumerable on the same terms as the CLI.** Tools are registered
  through `register_*_tools` in `src/vaultspec_core/mcp_server/app.py:141` and read back
  with `await mcp.list_tools()`. The generator's marker grammar and `MANAGED_FILES`
  registry are already file-agnostic, so bringing `docs/MCP.md` under the same contract
  is a registry entry and a renderer, not a second generator.

- **The generated block is load-bearing.** `src/vaultspec_core/mcp_server/catalog.py`
  parses the `command-inventory` region to close the `discover`/`invoke` gateway over a
  known verb set. Any new region must be a sibling of that block, never a change to it,
  so the gateway's input is untouched by this work.

## Considered options

- **Hand-maintained per-command caveats (status quo).** Rejected. It is the growing
  correction layer the problem names, it covers two of six affected commands today, and
  its wording is the expiring-caveat shape the release-provenance guards were written to
  prevent.

- **Derive the published surface from git tags at generation time.** Rejected. It needs
  tags present at generation, which shallow CI clones do not have, and it leaves the
  post-publication check with no immutable artifact to verify against.

- **Publish documentation only from release tags.** Rejected. It answers the provenance
  question by removing the main-branch document, which is the document contributors and
  the MCP gateway read. The problem is that the main-branch surface is unattributed, not
  that it exists.

- **Commit a published-surface snapshot, refresh it on the candidate branch, verify it
  against the published artifact.** Chosen. It is offline and deterministic, it makes the
  HEAD-only set a computed difference rather than an assertion, and it gives the release
  lane one immutable object to check.

## Constraints

- **The `command-inventory` region's rendering does not change.** It is the gateway's
  verb-existence source per the `cli-reference-automation` decision. New content is a new
  region beside it.

- **No claim may expire.** Generated attribution states what is true at render time and
  is recomputed on the next render. No document may name a future version, and no guard
  may be written so that cutting a release turns it red.

- **The snapshot is data, not prose.** It is a machine-written artifact under
  `builtins/`, refreshed only by its owning verb, and hand-editing it is the same class
  of error as hand-editing a managed region.

- **`--check` stays correct inside an installed wheel.** The handbook and any
  source-only surface remain `optional` in the registry, so a wheel checks what it ships
  and no more.

- **No new dependency.** Typer/Click introspection, the MCP server's own `list_tools`,
  and the standard library are the whole toolset, as the parent generator decision
  requires.

## Implementation

A committed snapshot records the published surface. It is a machine-written JSON
artifact under `src/vaultspec_core/builtins/reference/`, holding the published version
string, the CLI verb paths, and the MCP tool names of the release named by that version.
It is written only by its owning verb, which captures the live surface and stamps it with
the tree's own version.

`release-please.yml` runs that verb on the release pull request's branch, where the
version is the candidate's and the tree is main's, and pushes the result onto the branch
beside the `uv.lock` refresh it already performs. The snapshot therefore lands on main as
part of the release merge, describing exactly the surface that was tagged.

The generator gains one region rendered from the difference between the live surface and
the snapshot: the verbs and tools present on HEAD and absent from the published release,
under a heading that names the published version. When the difference is empty the region
says so. That region carries the attribution the hand-written caveat carried, for every
affected command rather than two, and it retires itself on the next release without being
edited.

`docs/MCP.md` joins `MANAGED_FILES` with a tool-inventory region rendered from
`mcp.list_tools()`, so the MCP surface is generated and attributed on the same terms as
the CLI, and drifts loudly instead of silently.

`publish.yml` gains a job that reads the published distribution back - the same isolated
install its smoke test already uses - enumerates its surface, and compares it against the
snapshot committed at the tag. A mismatch fails the release lane: it means the document
published for that version describes a surface that version does not have.

The hand-written `0.1.73` caveat in `docs/CLI.md` is deleted, because the generated
region now states the same fact for every command it applies to.

## Rationale

The contract is chosen so that each claim is made where it can be true and checked where
it can be proven. Generation on the candidate branch is the only point at which the
version and the surface belong to each other; verification against the published artifact
is the only point at which the claim stops being a build-time assertion about source and
becomes a statement about what users install.

Making the HEAD-only set a computed difference, rather than authored prose, is what
retires the correction layer permanently. A hand-written caveat has to be added when a
command lands and removed when it ships, and both edits are silent when skipped - the
present state, where four of six affected surfaces were never given a caveat at all. A
rendered difference has no skipped state.

The snapshot is committed rather than derived because both consumers need it to be
available without a network or a full tag history, and because the post-publication check
requires something immutable at the tag to compare against. Its cost is one refresh step
on a branch that already takes one.

## Consequences

- The release lane gains a gate it did not have: a release whose published surface
  disagrees with its committed snapshot fails after publication rather than shipping a
  reference that describes a different program.

- A second machine-owned artifact joins the managed-region discipline. Hand-editing the
  snapshot is a new failure mode, mitigated the same way managed regions are - the owning
  verb rewrites it and the check fails until it matches.

- Between releases, the generated references carry a visibly non-empty unreleased-surface
  region. This is the intended state and the accurate one; readers who need the released
  surface read the snapshot's version, and consumers can filter mechanically.

- The MCP reference comes under generation for the first time, so its tool section gains
  a drift gate it has never had. Its hand-written per-tool prose stays hand-written; only
  the inventory is generated.

- Honest cost: the snapshot refresh runs on the release-please branch, which is
  regenerated and force-pushed. The step must be idempotent and must not fail the release
  when the snapshot is already current, or it becomes the release-pressure repair the
  provenance guards were written to avoid.

## Codification candidates

- **Rule slug:** `published-surface-snapshot-is-verb-owned`. **Rule:** The published
  surface snapshot is written only by its owning verb on the release candidate branch;
  it is never hand-edited, and a release whose published artifact's surface differs from
  the snapshot committed at its tag fails the publish lane.

- **Rule slug:** `attribution-never-expires`. **Rule:** Version-scoped claims in
  generated references are rendered from the live surface against the published
  snapshot, never authored as prose naming a version, so that cutting a release can
  never turn a document or a guard false.
