---
tags:
  - '#adr'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-09-firmware-wording-review-research]]'
---

# `cli-reference-automation` adr: `cli reference auto-generation` | (**status:** `accepted`)

## Problem Statement

The bundled machine-facing reference at `src/vaultspec_core/builtins/reference/cli.md`
is hand-authored. It lists the full command inventory, per-command option tables,
argument enumerations, exit codes, and the environment-variable table for every
`vaultspec-core` verb, and it seeds into every consumer workspace on install. Because it
is hand-authored, it drifts from the live Typer surface every time a command, flag,
default, or enumeration changes, and that drift must be corrected by hand on two surfaces
at once (this reference and `docs/CLI.md`).

The firmware-wording-review decision record deferred this problem as decision D6: it
hand-updated the reference to the live 0.1.26 surface and logged automated regeneration
as a follow-up rather than building it. This ADR resolves that deferral. The follow-up
plan's `P02.S04` opens with this decision and gates the generator implementation and the
CLI-rule documentation behind it. The user has decided to build the generator: it is
valuable because it removes the manual two-surface update burden, and it guards against
the regression the hand-authored surface keeps re-introducing.

Today an enforced drift guard already prevents one half of the problem.
`src/vaultspec_core/tests/cli/test_cli_reference_drift.py` walks the live Typer tree,
invokes `--help` on every visible leaf command, and asserts that every command name and
every non-global option name appears somewhere in the bundled reference. Drift is
therefore detected at CI time. What the guard cannot do is fix the drift: when a flag
lands without a reference edit, the guard fails red and a human must locate the gap and
patch the markdown by hand. This ADR decides to add the missing half - a generator that
auto-produces the derivable content - while keeping the drift guard as the backstop.

## Considerations

The investigation grounded the decision in the live code.

- **Typer introspection is feasible and already proven.** Both existing drift guards
  (`test_cli_reference_drift.py` and `test_cli_handbook_drift.py`) walk the Typer app
  object exported from `vaultspec_core.cli` via `registered_commands` and
  `registered_groups`, descending `group.typer_instance` recursively to enumerate every
  visible leaf command and sub-group, skipping `hidden` entries. Per-command option
  metadata is recovered by invoking `--help` through Typer's `CliRunner` and parsing the
  rendered option box. The same Typer/Click introspection the guard relies on - command
  names, argument names, option long and short forms, defaults, help strings, and
  `Choice`/enum argument enumerations - is reachable programmatically through the Click
  `Command` and `Parameter` objects Typer builds, so a generator can read the same tree
  the guard already walks. No new dependency is required; Typer and Click are already in
  the stack and already introspected by the test suite.

- **The reference is a hybrid of derivable structure and hand-written prose.** Mapping
  the current `cli.md` against the Typer tree shows two distinct content classes.
  Mechanically derivable from introspection: the command-inventory signature block (every
  leaf signature with its `[OPTIONS]`/argument shape), the per-command option tables
  (option name, short form, default, and the help string Typer already carries), the
  argument enumerations (provider choices, `DOC_TYPE` values, doc-type enums), and the
  exit codes where they are declared. Not mechanically derivable: the prose framing and
  grouping narrative (the "Entry points" table that names `vaultspec-mcp` and the module
  invocation, the "Global options" prose paragraph about `--target` propagation, the
  "Sync output vocabulary" section, the grouped CRUD-shape table for
  `rules`/`skills`/`agents`, the consolidated `vault check` and `vault plan` narrative
  paragraphs, and the environment-variable table whose values live in the config layer,
  not the CLI surface). A pure dump of the Typer tree would lose all of this curated
  prose and produce a flat, less usable artifact. The generator must therefore preserve
  the hand-written zones rather than overwrite them.

- **The generator's home is the `spec` command group.** The Typer `spec` group already
  hosts CRUD groups (`rules`, `skills`, `agents`, `hooks`, `mcps`), resource-scoped
  `system`/`sync` verbs, and a top-level `doctor` command. A reference generator is a
  framework-resource maintenance verb of exactly that kind. Mounting it as
  `vaultspec-core spec reference generate` (with a `reference` sub-group or a single
  command) keeps it discoverable beside the resources it documents and lets it reuse the
  existing renderer and target-resolution helpers. A loose `scripts/` entry point or a
  bare module would be invisible to the CLI surface it documents and would not inherit
  the `spec doctor`/sync ergonomics. The verb may be marked `hidden=True` if it is
  intended as a developer/CI tool rather than a consumer-facing one; the drift guards
  skip `hidden` entries, so a hidden generator verb does not pollute the very reference
  it produces.

- **A `--check` mode composes the generator with the existing guard.** The generator
  runs in two modes from one code path: a write mode that regenerates the bundled
  reference in place, and a `--check` mode that generates into memory, compares against
  the committed `cli.md`, prints the diff, and exits non-zero when they differ. CI runs
  `--check`; pre-commit runs `--check` (or the write mode, leaving the staged result for
  the author to review). The existing drift guard is retained unchanged as an
  independent backstop: the guard asserts coverage (every command and flag is mentioned),
  while the generator asserts byte-fidelity of the managed zones (the reference equals
  fresh output). The two are complementary - the guard catches a hand-edit that the
  generator's managed regions do not cover, and the generator catches drift the guard's
  substring search would pass.

## Constraints

- **Hand-written zones must survive exactly.** The current `cli.md` carries curated prose
  (entry-point table, global-options narrative, sync-vocabulary section, grouped CRUD
  table, consolidated `vault check`/`vault plan` paragraphs, environment-variable table)
  that introspection cannot infer. The generator must either reproduce these zones
  byte-for-byte by sourcing them from a preserved region scheme (explicit
  managed/unmanaged markers around the derivable blocks, or a hybrid where prose is
  authored in command docstrings and rendered) or carry them as authored fragments it
  composes around the generated tables. No prose content may be lost in the conversion;
  the converted reference must be functionally equivalent to today's at its current
  surface.

- **American spelling and `mdformat --wrap 88` conventions hold.** Generated output is
  markdown under `builtins/`; it must pass the same `mdformat --wrap 88` formatting and
  American-spelling conventions the rest of the firmware obeys, so the generator emits
  pre-wrapped, pre-formatted markdown (or its output is piped through `mdformat` as a
  final pass) and never emits British spellings in generated prose.

- **No new heavy dependencies.** The generator uses the Typer/Click introspection already
  resident in the stack and already exercised by the drift guards. It must not add a
  markdown-extraction library, a separate doc-build toolchain, or a templating engine
  beyond what is already vendored; the rendering is plain string assembly over the
  introspected tree.

- **The generator depends on a stable Typer surface.** The Typer app object exported from
  `vaultspec_core.cli` is the single source of truth the generator reads. That surface is
  mature and stable (it backs two existing drift guards), so this is a low-risk parent
  dependency; the generator inherits whatever the live tree exposes and stays correct by
  construction as the tree evolves.

## Implementation

The generator is a `spec`-group verb (`vaultspec-core spec reference generate`) that
introspects the Typer app object and emits the bundled reference. It walks the command
tree exactly as the existing drift guard does - `registered_commands` and
`registered_groups`, descending recursively and skipping `hidden` entries - and reads
per-command argument and option metadata from the Click parameter objects (names, short
forms, defaults, required-ness, help strings, and `Choice` enumerations). From that tree
it renders the mechanically derivable zones: the command-inventory signature block, the
per-command option tables, the argument enumerations, and the declared exit codes.

The hand-written zones are preserved through a managed-region scheme: the derivable
blocks sit inside explicit managed markers that the generator owns and rewrites, while
the curated prose (entry-point table, global-options narrative, sync-vocabulary section,
grouped CRUD table, the consolidated `vault check`/`vault plan` paragraphs, and the
environment-variable table) lives in unmanaged regions the generator reads but never
rewrites - or, where the prose is naturally per-command, is sourced from the command
docstrings Typer already carries and rendered into the managed block. The conversion of
today's hand-authored `cli.md` into this region scheme must preserve every existing prose
zone without loss.

The verb runs in two modes from one rendering path. The default write mode regenerates
`cli.md` in place. A `--check` mode renders into memory, compares against the committed
file, reports the diff, and exits non-zero on mismatch; this is the CI and pre-commit
entry point. Generated markdown is emitted pre-formatted to the `mdformat --wrap 88`
convention (or finalized through an `mdformat` pass) so the committed artifact and the
generator output never disagree on whitespace alone.

The existing drift guard (`test_cli_reference_drift.py`) is retained unchanged as an
independent backstop. The guard asserts coverage; the generator asserts byte-fidelity of
the managed regions. CI runs both: the generator's `--check` mode fails the build when
the committed reference diverges from fresh output, and the guard fails the build when a
command or flag is uncovered. The downstream plan Steps (`P02.S05`, `P02.S06`) implement
this generator with covering tests and document it in the CLI rule as the canonical
reference-update path.

## Rationale

The build decision is user-confirmed: the generator is valuable and it is
regression-safe. The valuable half is that it removes the manual update burden the prior
`bundled-cli-reference` ADR explicitly accepted as the cost of hand-authoring - that ADR
chose hand-authoring-plus-drift-guard precisely because a generator "adds build
machinery" and a generated artifact "must either be tracked or built on every package
build". The intervening firmware-wording-review campaign demonstrated that cost in
practice: D6 had to hand-reconcile the reference to the live surface, and the audit's
`REVIEW-005` lineage and the `P01.S03` reference-accuracy gap are the recurring symptom
of a hand-maintained surface. The regression-safe half is that the generator's `--check`
mode converts a detect-only guard into an auto-fix-plus-gate: drift is not merely caught,
it is mechanically corrected, and CI gains a generated-content-up-to-date gate.

This ADR narrows rather than contradicts the prior `bundled-cli-reference` decision. That
ADR rejected a generator that would extract the reference from `docs/CLI.md` by parsing
markdown - a markdown-extraction build step over a second document. This ADR builds a
different generator: one that introspects the live Typer object directly (the same object
the drift guards already walk), adds no markdown parser, and preserves the curated prose
through managed regions. The introspection feasibility, the derivable-versus-prose split,
and the existing guard's proven tree walk are the grounding evidence that this narrower
generator is buildable without the build-machinery cost the prior ADR feared.

## Consequences

- The framework gains a renderer to maintain: the mapping from the introspected Typer
  tree to the reference's managed zones is code that must track Typer/Click API shifts.
  This is bounded - the two existing drift guards already carry the same introspection
  burden, so the renderer shares their maintenance surface rather than opening a new one.

- The managed/unmanaged-region discipline becomes a standing obligation: contributors
  must understand that the derivable zones are generator-owned and must not be hand-edited
  (hand edits are overwritten on the next generate), while the curated prose zones remain
  hand-authored. Mislabeling a region, or hand-editing a managed zone, is the new failure
  mode the codification candidate below guards against.

- CI gains a generated-content-up-to-date gate: the `--check` mode fails the build when
  the committed reference diverges from fresh output. This is a net tightening - drift
  that previously required a human to notice and fix now fails the build deterministically
  and is fixed by re-running the generator.

- The decision opens a clear path to the sibling references the prior ADR scoped out
  (`mcp.md`, `framework.md`): once the introspection-plus-managed-region pattern is proven
  on `cli.md`, the same renderer shape extends to the other bundled surfaces.

- Honest cost: the conversion of today's hand-authored `cli.md` into the managed-region
  scheme is a one-time migration that must preserve every curated prose zone exactly. If
  that conversion drops or garbles a prose zone, the regression lands in the consumer
  artifact; `P02.S05`'s acceptance bar (regenerate the reference at its current surface
  without loss) and the retained drift guard are the controls against it.

## Codification candidates

- **Rule slug:** `generated-reference-is-cli-owned`.
  **Rule:** The bundled CLI reference's generator-managed regions are updated only by
  running `vaultspec-core spec reference generate`, never by hand-editing the managed
  markdown; hand edits inside a managed zone are overwritten on the next generate and the
  `--check` mode fails CI until the reference matches fresh output.
