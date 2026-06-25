---
tags:
  - '#research'
  - '#cli-presentation-uniformity'
date: '2026-06-24'
modified: '2026-06-24'
related: []
---

# `cli-presentation-uniformity` research: `CLI presentation inventory and the rag/glow plain-format target`

This research inventories the current `vaultspec-core` presentation surfaces (help, hints, data output) and fixes the target shape against two external reference tools, `uvx vaultspec-rag` and `glow`, to ground the `cli-presentation-uniformity` decision. It establishes what is non-conforming, why, and what the conforming target is.

## Findings

### F1 - The target shape is plain Click help, observed in two reference tools

`vaultspec-rag --help` and `glow --help` both render bog-standard command-line help: a `Usage:` line, a wrapped prose description, and flat `Arguments:` / `Options:` / `Commands:` sections with no borders. Neither carries an inline `Examples:` block in its top-level help. `vaultspec-rag status` shows the data target: a bold header, `Label: value` lines, and a `Next action:` footer with the suggested command indented beneath. This is the exact shape vaultspec-core must match, for help and data.

### F2 - All help renders as Rich panels because no Typer app sets `rich_markup_mode`

The CLI defines seventeen `Typer` apps across six files: one in `root.py`; six in `vault_cmd.py` (`vault_app`, `feature_app`, `check_app`, `sanitize_app`, `rule_app`, `adr_app`); eight in `plan_cmd.py` (`plan_app`, `step_app`, `phase_app`, `wave_app`, `epic_app`, `tier_app`, `trailer_app`, `epic_intent_app`); nine in `spec_cmd.py` (`spec_app`, `rules_app`, `skills_app`, `agents_app`, `system_app`, `hooks_app`, `mcps_app`, `reference_app`); plus `config_app`, `migrations_app`, and `link_app`. None sets `rich_markup_mode`, so every one inherits Typer's panel default and draws bordered `Options` and `Commands` boxes. Setting `rich_markup_mode=None` makes Typer fall back to Click's standard `HelpFormatter`, which reproduces the F1 shape and wraps to terminal width. This was verified directly: a `None`-mode app with a sub-app renders plain `Usage`/`Options`/`Commands` with no borders.

### F3 - Plain Click collapses multi-line help, so inline examples must move out

A multi-line `help=` string (the root app's `Examples:` block, plus inline examples in `config_cmd.py` and `migrations_cmd.py`) is reflowed by Click into a single paragraph, mangling the examples into a run-on. The reference tools carry no inline examples in top-level help. The resolution is to drop the `Examples:` blocks from help strings and host worked invocations in the bundled CLI reference, keeping help to a one-line summary plus a short wrapped description.

### F4 - Help and option text conventions are inconsistent

Option help strings mix capitalization (`Target directory ...` vs `name of the promoted rule`) and trailing periods (present on some, absent on most). There is no single convention. The target is imperative sentence case with a terminal period, uniform across the surface.

### F5 - The hint mechanism is sound but rendered in several forms

The `cli-next-step-hints` decision is implemented: a static `(command, outcome)` table feeds `emit_next_step_hint`, with `--no-hints` / `VAULTSPEC_NO_HINTS` suppression and a JSON `next_step` field. There are ten call sites of the shared helper. But the rendered form is `Suggested Next Step:` with a `>` prefix, and several surfaces emit ad-hoc next-step text outside the helper: sync upgrade and warning footers in `root.py`, the status rollup and trace hint pairs in `status_cmd.py`, and a migrations suggestion line in `migrations_cmd.py`. The mechanism is kept; only the rendered form is unified to one `Next action:` footer and every ad-hoc surface is rerouted through the helper.

### F6 - Eight data surfaces never adopted the standardization contract

Most data output routes through the four shared shapes, but these surfaces still hand-format: `vault stats` (manual key/value lines), `vault list` (hand-formatted space-separated rows), `vault graph` metrics (manual per-type, per-feature, and centrality loops), the `vault repair` run report (a complete bypass with phase-specific custom formatting), both `status` modes (rollup with manual alignment, trace with checkbox glyph escaping), `migrations status` (manual status loop), and `doctor`, which alone carries two divergent internal styles. Each needs converting to a Record, Listing, or Tree payload routed through the shared emitter.

### F7 - Four glyph vocabularies coexist

The outcome and dry-run renderers use the ASCII set `+ ~ - = * !`. Separately, preflight rendering uses `ok` / `FAIL` / `x` / `!` / a bullet, the status trace uses escaped `[x]` / `[ ]` checkboxes plus a `>` cursor, and migrations uses `unknown` / `pending` / `applied` words. Collapsing these to the single ASCII status set gives a reader one vocabulary to learn.

### F8 - Width-determinism and terminal wrapping are not in conflict

The `cli-output-standardization` decision banned width-derived layout for byte-determinism. The requirement that output wrap on a narrow terminal does not reverse that: a renderer that lays out columns by terminal width is banned; a plain string line that the terminal soft-wraps is fine. Help uses Click's native wrapping; data renderers keep emitting plain, width-independent strings, and the terminal remains free to wrap long lines. The contract is refined, not reversed.

### F9 - Test coupling is shallow

The existing no-box determinism test asserts on the data path and is extendable to assert the same for `--help` (no panel border or box-drawing glyph) and to assert narrow-width wrapping and a single hint footer form. No test asserts on the framed help today, so disabling Rich help breaks no existing assertion; the bundled CLI reference drift test is the surface that regenerates to host relocated examples.
