---
tags:
  - '#adr'
  - '#bundled-cli-reference'
date: '2026-05-18'
modified: '2026-05-18'
related:
  - '[[2026-05-18-bundled-cli-reference-research]]'
  - '[[2026-05-17-vaultspec-source-layout-collapse-adr]]'
---

# `bundled-cli-reference` adr: `bundle a hand-authored machine-facing CLI reference under builtins/reference/` | (**status:** `accepted`)

## Problem Statement

The source-layout-collapse ADR moved the human-facing documentation
(`CLI.md`, `MCP.md`, `framework.md`) into a top-level `docs/` directory and
left the bundled rule `vaultspec-cli.builtin.md` pointing at those documents
via GitHub URLs. Consumer projects that install vaultspec therefore have no
locally-resident command reference: an AI agent operating in a consumer
project must either fetch a GitHub URL or shell out to `--help` to discover
the command surface. The source-layout-collapse ADR explicitly deferred the
fix as a follow-up: bundle a leaner machine-facing operational reference
into the package so it seeds into consumer projects on install.

This ADR decides the shape of that bundled reference: where it lives in the
package, how consumers receive it, how it stays correct against the live
CLI, and how the existing bundled rule connects to it.

## Considerations

The research record establishes the controlling constraint: every `*.md`
file under `builtins/rules/` is discovered by the rule pipeline and
assembled into provider configuration with `trigger: always_on`. A
comprehensive CLI reference is several hundred lines; placing it under
`builtins/rules/` would inflate every consumer's provider configuration on
every sync. The reference must be bundled and seeded but must not be a rule.

`seed_builtins` copies the entire `builtins/` tree into the consumer's
`.vaultspec/rules/` directory, preserving subdirectory structure. The sync
pipeline dispatches only over the known resource subdirectories (`rules`,
`skills`, `agents`, `system`, `mcps`). A new subdirectory that is none of
those is seeded into the consumer workspace but is inert to every sync
pass: locally present and readable, never assembled into provider
configuration.

`docs/CLI.md` is kept synchronized with the live Typer command surface by
`test_cli_handbook_drift.py`, which walks every leaf command and asserts
its name and options appear in the document. That drift guard is why
`docs/CLI.md` is a trustworthy reference. Any bundled reference that is
hand-authored needs an equivalent guard, or it will silently fall out of
step with the CLI.

A build-time generator that extracts the bundled reference from
`docs/CLI.md` would inherit the existing drift protection, but it adds
build machinery, produces a generated artefact that must either be tracked
(and can drift from its generator) or built on every package build (a new
failure surface), and couples the bundled-content build to a markdown
parser. The framework's established pattern is author-in-markdown,
let-tools-consume; a hand-authored reference with its own drift test fits
that pattern and avoids the generator.

## Constraints

The bundled reference must seed into consumer projects through the existing
`seed_builtins` path without any change to the seeding mechanism.

The bundled reference must not be discovered by the rule pipeline. It must
not appear in any provider's assembled configuration.

The bundled reference must not trip `vault check` or `spec doctor`. Those
diagnostics operate on `.vault/` documents and on the known provider
resource types; a new inert subtree under `.vaultspec/rules/` must be
verified to leave them silent.

The bundled reference must have a drift guard that fails CI when the live
CLI surface changes without a corresponding reference update, matching the
protection `docs/CLI.md` already enjoys.

The existing `vaultspec-cli.builtin.md` rule must continue to be the
lightweight always-on cheat sheet. It must not absorb the reference
content. It gains a pointer to the bundled reference's local path so an
agent in a consumer project can find the reference without a network
round-trip.

## Implementation

A new subdirectory `src/vaultspec_core/builtins/reference/` holds a single
hand-authored file, `cli.md`, the machine-facing CLI reference. The file
is plain markdown with no rule frontmatter: it is a reference document, not
a rule. `seed_builtins` copies it to `.vaultspec/rules/reference/cli.md` in
every consumer project on install.

The reference content is a structured extraction of the machine-actionable
surface of `docs/CLI.md`: the full command and subcommand inventory, each
command's options with short forms, argument enumerations, exit-code
semantics, and the environment-variable table. It omits the human
narrative (prose rationale, worked examples, philosophy) that makes
`docs/CLI.md` long. It is organised as compact tables and lists optimised
for an agent scanning for a specific command or flag.

A new drift test, `test_cli_reference_drift.py`, walks the live Typer
command tree the same way `test_cli_handbook_drift.py` does and asserts
every command name and every non-global option appears in
`src/vaultspec_core/builtins/reference/cli.md`. This guarantees the bundled
reference cannot silently fall behind the CLI; a new command or flag fails
CI until the reference is updated.

The `vaultspec-cli.builtin.md` rule's references section gains a line
pointing at the local seeded path (`.vaultspec/rules/reference/cli.md`) so
an agent operating in a consumer project is directed to the
locally-resident reference first, with the GitHub URL retained as the
human-facing fallback.

The first iteration covers the CLI surface only. The MCP and framework
surfaces are explicitly out of scope; once the placement and drift-guard
pattern is proven on `cli.md`, a later iteration can add `mcp.md` and
`framework.md` siblings under the same `reference/` subdirectory.

## Rationale

Hand-authoring with a drift test is chosen over build-time generation
because it keeps the bundled content in the same author-in-markdown form
as every other file under `builtins/`, avoids adding a markdown-extraction
build step and a generated artefact, and still guarantees correctness: the
drift test fails the build the moment the reference and the live CLI
diverge. The cost is that a human updates two surfaces (`docs/CLI.md` and
the bundled reference) when the CLI changes; the drift tests on both make
that obligation explicit and enforced rather than silent.

The `builtins/reference/` placement is chosen because it is the only
option that is bundled, seeded, locally readable, and inert to the rule
pipeline and the sync passes. Nesting under a skill's `references/`
directory would mis-file a CLI-global reference under one skill; placing it
under `builtins/rules/` would make it an always-on rule.

## Consequences

Consumer projects gain a locally-resident CLI reference at
`.vaultspec/rules/reference/cli.md` after install. An AI agent operating in
a consumer project can read the full command surface without a network
round-trip or a shell-out to `--help`.

The framework now carries two CLI-surface drift tests: one for
`docs/CLI.md`, one for the bundled reference. A CLI change that adds or
renames a command or flag fails both until both surfaces are updated. This
doubles the update obligation but makes both surfaces trustworthy.

A new inert subtree appears under every consumer's `.vaultspec/rules/`.
Because `.vaultspec/` is gitignored in consumer projects (per the
source-layout-collapse contract), the seeded reference does not appear in
consumer versioning; it is a pure install artefact, refreshed on every
`install --upgrade`.

The `reference/` subdirectory establishes a precedent: future bundled
machine-facing references (MCP, framework) have an obvious home. The ADR
scopes the first iteration to the CLI surface so the pattern is proven
once before it is extended.
