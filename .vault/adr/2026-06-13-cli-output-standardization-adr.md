---
tags:
  - '#adr'
  - '#cli-output-standardization'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-cli-output-standardization-research]]'
  - '[[2026-06-13-status-hardening-research]]'
  - '[[2026-05-17-cli-json-consistency-adr]]'
  - '[[2026-05-17-cli-sync-vocabulary-adr]]'
  - '[[2026-05-17-cli-simplification-ux-adr]]'
---

# `cli-output-standardization` adr: `the vaultspec cli output contract` | (**status:** `accepted`)

## Problem Statement

The primary reader of `vaultspec-core` output is a large language model operating
the CLI through a tool harness, not a human at a terminal. The state-changing
surfaces already respect this: the `cli-sync-vocabulary` and `cli-json-consistency`
decisions gave them a box-free, summary-terminated, dual-text-and-JSON contract.
The read surfaces never inherited it. The `list`, `status`, `show`, and `doctor`
families still render through Rich `Table`, `Panel`, and `Tree` constructs built
for human eyes.

The companion research inventories roughly thirteen `Table` surfaces and finds
three structural defects (findings F1-F3). They are **token-hungry**: every border,
separator, and divider is a run of multi-byte box-drawing glyphs, every cell is
right-padded to its column width, and the reader must count rows because no
aggregate is emitted. They are **non-deterministic**: `get_console()` passes no
fixed width and does no tty/CI detection, so the same command on the same data
emits different bytes under a wide terminal, an 80-column pipe, and a CI log, and
the `safe_box` toggle swaps the glyph set again between UTF-8 and cp1252 stdout.
And they are **incompletely machine-readable**: the `vault plan` mutators,
`vault rule promote`, and `vault adr supersede` emit a bare string or a diff with
no `--json` surface at all (F5).

This is the "flaky, token-hungry, formatting breaks" report. It is also a blocker
for the sibling status-hardening work, whose blind reviewers independently hit the
same layer ("an unreadable wall", "titles truncated mid-sentence", "floods the
view"). A clean status surface cannot sit on a rendering layer that breaks. This
ADR codifies the output contract that fixes the foundation.

## Considerations

- **The pattern already exists in-repo.** `render_outcomes` plus `outcomes_as_json`
  over a single `OutcomeItem` list is the proven shape: one glyph-prefixed line per
  item, a terminating per-outcome count, no boxes, no width padding, and text whose
  values equal the JSON values. The contract generalizes this rather than inventing
  a format.

- **Determinism is about width, not alignment.** Data-derived column alignment
  (pad to the longest value in the current rows) is a pure function of the data and
  is stable across environments. The instability comes only from terminal-width and
  encoding-derived layout. So alignment is not banned for being non-deterministic;
  it is weighed purely on token cost.

- **Token cost favors single-space fields.** Aligned columns aid a human scanning a
  wide terminal but spend padding whitespace that a parser ignores. A single-space
  field separator with a stable field order is the cheapest stable form. This ADR
  recommends single-space, no padding. (This is the one sub-decision worth explicit
  sign-off: a reader who values human scanning may prefer data-derived alignment,
  which is also env-stable but costs tokens. The contract is written for the
  single-space default and notes the alignment variant as the documented
  alternative.)

- **Color must be redundant.** Rich already strips ANSI on a pipe, and an LLM gains
  nothing from it. The contract permits color as decoration but forbids carrying any
  state in color alone, so a `NO_COLOR` or piped run loses no information.

- **Truncation must be fixed and marked.** Long free-text fields truncate to a
  constant character budget with an explicit marker, never to a width-derived bound;
  the full value stays available under `--json`.

- **Text is a courtesy; JSON is the contract.** Scraped table text was never a
  stable interface. Making the plain text deterministic helps humans and cheap LLM
  reads, but `--json` via the versioned envelope remains the machine contract.

- **Migration is incremental and the test coupling is shallow** (F6): no test
  asserts on box-drawing characters or uses snapshots, so surfaces convert one at a
  time and the determinism guarantee is itself a cheap test.

## Constraints

- **Rich stays a dependency.** Typer renders `--help` through Rich, and the contract
  governs vaultspec's own *data* output only, not Typer's help panels. This narrows
  Rich's use; it does not remove the library.

- **Parent contracts are stable and must not regress.** This decision builds
  directly on the shipped, mature `Outcome` taxonomy and the `json_envelope` shape.
  Both are in-tree, in-training-cutoff, and carry no frontier risk; the new shapes
  must extend them, never fork them. The `Outcome` shape is adopted verbatim as one
  of the four shapes.

- **One-time text break is accepted.** Any tooling that scraped the old table text
  breaks. This is acceptable because table text was never a documented contract and
  `--json` already covers every read surface that mattered; the gap closure (F5) is
  part of this work, not a casualty of it.

- **cp1252 handling is simplified, not deleted.** An ASCII-only glyph set in the
  data path makes `safe_box` moot for vaultspec output, but `console.py` stays
  because Typer help still needs the UTF-8 stdio hardening.

- **No new or unstable technology.** This is a consolidation onto an existing,
  proven internal pattern. The only constraint is discipline: preventing future
  surfaces from reintroducing box-drawing (addressed under codification).

## Implementation

The contract defines **four output shapes**, each a small payload object in
`cli/rendering.py` with one text renderer and one JSON renderer that consume the
same object, exactly as `OutcomeItem` feeds both `render_outcomes` and
`outcomes_as_json` today. No command hand-formats output; it builds a payload and
hands it to the shared emitter.

- **Record** - one entity's fields. Replaces the `field / value` two-column status
  tables (`spec rules status`, `spec hooks status`, `spec mcps status`,
  `vault stats`, `vault graph --metrics`).
- **Listing** - a flat sequence of items each carrying a small fixed field set.
  Replaces `spec rules/skills/agents/hooks/mcps list`, `config list`, `vault list`.
- **Tree** - genuinely hierarchical data. Replaces the Rich `Tree` renderers
  (vault graph default, dry-run preview) with indentation, not connector glyphs.
- **Outcome** - the existing state-changing shape, adopted unchanged, and extended
  to the mutators that currently lack `--json`.

**The plain-text rules** (the contract a reader implements against):

- A header line sits at column 0; items indent two spaces per nesting level. No
  blank-line padding between items.
- Fields render in a declared canonical order separated by a single space; the text
  field names equal the JSON keys. No padding-to-column-width.
- Every multi-item shape ends with exactly one **summary line**: a total and a
  parenthesized breakdown (the `render_outcomes` count line is the model).
- **Empty states are one explicit line** (`no rules`), never an empty table.
- Long free-text fields truncate to a fixed character budget with a trailing
  marker; the untruncated value lives in `--json`.
- The data path emits **no box-drawing characters and no `Panel` borders**;
  trees use indentation plus an ASCII status glyph set (`+ ~ - = *`), the set
  already used by the dry-run and outcome renderers.
- Output bytes do not depend on terminal width. Data lines are built as plain
  strings, not laid out by Rich's table or tree engine. Color, if present, is
  applied as markup over already-complete lines and is purely decorative.

**`--json` everywhere.** Every read shape serializes through `json_envelope`
(`{schema, status, data, hints}`), and every mutator missing a machine surface
(F5) maps onto the `Outcome` shape and gains `--json`.

**Migration.** Surfaces convert command by command. Each conversion deletes the
`rich.table` / `Panel` / `box` import from that call site, builds the appropriate
payload, and routes text and JSON through the shared emitter. Coupled tests update
in step: the substring assertions survive a reformat, and the single graph
tree-render test moves to the indentation form.

**Determinism as a tested invariant.** A contract test renders representative
surfaces under two different width and encoding environments and asserts the bytes
are identical, and asserts no box-drawing glyph appears anywhere in the data path.
This makes the central guarantee enforceable rather than aspirational.

## Rationale

The research recommends the least-invention path: the project already proved, on
its write surfaces, that a box-free, summary-terminated, single-payload dual
surface is both token-light and stable. Generalizing that one pattern to the read
surfaces - rather than designing a new format - keeps a single mental model across
the whole CLI, inherits the stable `--json` envelope, and closes the mutator gaps
in the same motion. It also unblocks status-hardening, whose one-line plan
enrichment and file-discovery output land cleanly only on a deterministic layer.
The decision is grounded in findings F1-F6 and constrained by the parent
`cli-sync-vocabulary` and `cli-json-consistency` decisions it extends.

## Consequences

- **Gains.** Output becomes deterministic across terminal width, tty/pipe, and
  stdout encoding; token cost on read surfaces drops sharply; every command reads
  through one shape vocabulary; the `--json` gaps close; cp1252 box-glyph handling
  becomes moot in the data path; a class of width-dependent formatting bugs
  disappears.

- **Costs, honestly.** It is a migration across roughly thirteen table surfaces
  plus their tests, done carefully one surface at a time. Humans lose the visual
  boxes; the mitigation is that indented lines with an explicit summary remain
  readable and the boxes carried no information. Anyone scraping the old table text
  breaks once; the mitigation is that `--json` is, and remains, the contract.

- **Pitfalls.** The real risk is drift: a future command author reaches for a
  `Table` again and silently reopens the wound. The mitigation is the determinism
  and no-box contract test plus the codified rule below, which makes a regression a
  failing build rather than a review-time judgment call.

- **Pathways opened.** Status-hardening's enrichment and file-path discovery become
  straightforward; new surfaces inherit the contract for free; and `console.py` can
  later shed its data-path `safe_box` complexity once no surface emits boxes.

## Codification candidates

- **Rule slug:** `cli-output-no-box-drawing`.
  **Rule:** Every `vaultspec-core` data surface (read or write) must render through
  the shared shape vocabulary in `cli/rendering.py`, emit no box-drawing characters
  or width-dependent layout, terminate multi-item output with a single summary
  line, and provide `--json` via the canonical envelope; the no-box and
  width-determinism guarantees are enforced by a contract test.
