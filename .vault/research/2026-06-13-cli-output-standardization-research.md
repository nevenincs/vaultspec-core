---
tags:
  - '#research'
  - '#cli-output-standardization'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - '[[2026-06-13-status-hardening-research]]'
  - '[[2026-05-17-cli-json-consistency-adr]]'
  - '[[2026-05-17-cli-sync-vocabulary-adr]]'
  - '[[2026-05-17-cli-simplification-ux-adr]]'
  - '[[2026-06-12-vault-orientation-adr]]'
---

# `cli-output-standardization` research: `plain line-protocol output contract for an llm-first cli`

The primary consumer of `vaultspec-core` output is a large language model, not a
human at a terminal. Yet the read surfaces of the CLI (the `list`, `status`,
`show`, and `doctor` families) render through Rich `Table`, `Panel`, and `Tree`
constructs designed for human eyes. This research inventories those surfaces,
quantifies why they are token-hungry and non-deterministic, and records the
prior-art the project already shipped for its state-changing surfaces, so the
companion ADR can extend that one proven contract to every remaining surface.

## Why this matters now

The sibling status-hardening review ran six blind testimonial agents against the
real vault and surfaced the same defect repeatedly from independent angles: the
targeted trace is "an unreadable wall", the feature graph's "titles are truncated
mid-sentence", and `--since` "floods the view" with hundreds of lines. Those are
not status-specific bugs; they are symptoms of a rendering layer that pads to
terminal width, wraps unpredictably, and spends tokens on box-drawing glyphs that
carry no information a model can use. Status hardening cannot deliver a clean
"zeroth move" on top of a rendering layer that breaks. The output contract is the
foundation; this research scopes it.

## Findings

### F1 - the table surfaces are the cost center (inventory)

A sweep of `src/vaultspec_core/cli/` found roughly thirteen Rich `Table`
constructions, all on read surfaces:

- `config list` (`config_cmd.py`): key / value / status.
- `spec rules list`, `spec skills list`, `spec agents list` (`spec_cmd.py`):
  name plus an ellipsized description column (`max_width=60` / `50`).
- `spec rules status`, `spec hooks status`, `spec mcps status` (`spec_cmd.py`):
  two-column field / value tables.
- `spec hooks list`, `spec mcps list`, `spec system show` (two tables),
  `spec doctor` and the root `doctor` (`spec_cmd.py`, `root.py`): component /
  status / detail.
- `vault graph --metrics` (`vault_cmd.py`): a borderless metric / value table.

Two `Panel` borders (`render_install_summary`, `render_uninstall_summary`) and
two `Tree` renderers (`render_dry_run_tree`; the vault graph default in
`graph/api.py`) round out the box-drawing surface.

### F2 - why tables are token-hungry

A Rich `Table` spends tokens on three things a model cannot consume:

- **Box-drawing glyphs.** Every rule line, header separator, and column divider
  is a run of multi-byte Unicode characters (the heavy box set the project uses
  by default on UTF-8 terminals). A single header border on a two-column table is
  tens of glyphs that tokenize poorly and convey nothing.
- **Padding to column width.** Rich right-pads every cell to the widest value in
  its column. A `name` column holding `vaultspec-system` pads every shorter row
  with trailing spaces, and those spaces are tokens.
- **No aggregate.** A table forces the reader to count rows. The model spends
  attention reconstructing a total the renderer already knew.

The state-changing surfaces already avoid all three (see F4); the read surfaces
did not inherit the discipline.

### F3 - why tables are non-deterministic (the "flaky" complaint)

`get_console()` in `console.py` builds its `Console` with `soft_wrap=True` and a
`safe_box` toggle for cp1252 streams, but passes **no explicit width and performs
no tty/CI detection**. Width therefore comes from Rich's environment probe:

- The same command emits **different bytes** under a 200-column interactive
  terminal, an 80-column fallback pipe, and a CI log. Layout is a function of the
  environment, not the data.
- `safe_box` swaps the box glyph set when stdout is not UTF-8, so the **same
  command on the same data produces a different glyph run** on a cp1252 Windows
  console versus a UTF-8 one. The install dry-run preview observed during this
  research truncated every path at the worktree-path width - a live reproduction.
- Long description columns truncate against a width Rich derived, not a fixed
  budget, so what gets elided also depends on the environment.

For an LLM consumer reading through a tool harness, this means the output schema
is unstable across runs and machines - the root of the "flaky / formatting
breaks" report.

### F4 - prior art: the project already solved this for write surfaces

The state-changing surfaces converged on a clean, line-oriented contract that is
exactly the model to generalize:

- The `cli-sync-vocabulary` decision defined a single `Outcome` enum (`created`,
  `updated`, `unchanged`, `removed`, `restored`, `skipped`, `failed`, `mixed`)
  and an `OutcomeItem` record. `render_outcomes` in `cli/rendering.py` prints one
  glyph-prefixed line per changed item, folds `unchanged` items into a count, and
  ends with a single per-outcome **summary line**. No boxes, no width padding, an
  explicit aggregate.
- The `cli-json-consistency` decision defined `json_envelope`: every `--json`
  output shares the shape `{schema, status, data, hints}`, versioned per command.
- Crucially, `render_outcomes` and `outcomes_as_json` **consume the same
  `OutcomeItem` list**, so the human and machine surfaces cannot drift. `Outcome`
  text equals `Outcome` JSON value.

This is the contract the read surfaces lack. The ADR's task is not to invent a
format; it is to lift this proven dual-surface, summary-terminated, box-free
pattern from `OutcomeItem` to the `list` / `status` / `record` / `tree` shapes
the tables currently serve.

### F5 - `--json` coverage is broad but not total

Most read commands already accept `--json` and route through `json_envelope`.
The gaps are the `vault plan` mutation verbs (`step`, `phase`, `wave`,
`epic intent`, `tier promote/demote`), plus `vault rule promote` and
`vault adr supersede`: these emit a bare `typer.echo()` string or a unified diff
with no machine surface at all. Any standard that mandates a parseable contract
must close these, mapping the mutators onto the existing `Outcome` shape.

### F6 - the test coupling is shallow

No test asserts on Unicode box-drawing characters or uses a snapshot library.
Coupling to the current rendering is limited to substring checks on words that
will survive a reformat (`"framework"`, `"builtins"`, `"1 created"`,
`"up to date"`, `"(not created)"`), with a single test in `graph/tests/` that
renders a `Tree` to a fixed-width buffer. A migration can proceed surface by
surface without a snapshot rewrite, and the determinism guarantee is itself
testable (assert identical bytes under two different width environments).

## Token comparison (illustrative)

`spec rules list` with three rules, rendered as the project's current heavy-box
table, spends a header border, a header row, a header separator, three padded
data rows, and a bottom border - on the order of a hundred-plus tokens dominated
by glyphs and padding. The same data as indented `name source` lines plus one
summary line is a small fraction of that, carries the aggregate explicitly, and
is byte-identical regardless of terminal width or stdout encoding.

## Design considerations for the contract

- **Determinism beats alignment.** Column padding aids a human scanning a wide
  terminal but is value-dependent whitespace that costs tokens and gives a parser
  nothing. A single-space field separator with a stable field order is both
  cheaper and more stable than aligned columns.
- **Color must be redundant.** Rich strips ANSI on a pipe already; the contract
  must guarantee no information lives in color alone, so a `NO_COLOR` or piped run
  loses nothing. Every state encoded as a color must also be a word or glyph.
- **Truncation must be fixed and marked.** Long free-text fields should truncate
  to a constant character budget with an explicit marker, never to a
  width-derived bound, and the full value stays available via `--json`.
- **One shape vocabulary.** The read surfaces reduce to four shapes - a single
  record (field/value), a flat listing (rows), a tree (genuinely hierarchical),
  and the existing outcome list. A small shared vocabulary in `cli/rendering.py`,
  each shape with a text renderer and a JSON renderer over one payload object,
  prevents per-command hand-formatting and the drift it causes.
- **Text is not the contract; JSON is.** Scraped table text was never a stable
  interface. Making the plain text deterministic is a courtesy to humans and
  cheap LLM reads; `--json` remains the versioned machine contract.

## Recommendation for the ADR

Codify a single output contract - "the vaultspec CLI output contract" - that
bans box-drawing and width-dependent layout from the data path, defines the four
plain-text shapes over a shared payload model mirroring `OutcomeItem`, mandates a
terminating summary line and explicit empty states, requires `--json` on every
read and write surface, and pins determinism (identical bytes across terminal
widths and stdout encodings) as a tested invariant. The migration is incremental
and per-surface; the contract is the durable artifact and a strong codification
candidate (no new CLI surface may reintroduce box-drawing).
