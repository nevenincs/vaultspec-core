---
tags:
  - '#adr'
  - '#cli-presentation-uniformity'
date: '2026-06-24'
modified: '2026-06-25'
related:
  - "[[2026-06-13-cli-output-standardization-adr]]"
  - "[[2026-05-17-cli-next-step-hints-adr]]"
  - '[[2026-06-24-cli-presentation-uniformity-research]]'
---

# `cli-presentation-uniformity` adr: `Bog-standard CLI presentation: plain help, uniform hints, no Rich tables` | (**status:** `accepted`)

## Problem Statement

The `cli-output-standardization` decision gave vaultspec's own data output a box-free, summary-terminated contract, but it drew its scope boundary at vaultspec's data only and explicitly left Typer's `--help` rendering to Rich. The result is a CLI that presents two unrelated visual languages. Every `--help` screen renders through Rich's panel engine: bordered `Options` and `Commands` boxes drawn with multi-byte box-drawing glyphs, padded to terminal width, that look nothing like the data the same binary prints a moment later. A reader who runs `vaultspec-core spec --help` sees a framed table; a reader who runs `spec rules list` sees plain indented lines. Neither the operator nor the language model driving the tool gets one consistent surface.

The reference points are deliberate and external. `uvx vaultspec-rag --help` and `glow --help` are bog-standard, legible, robust command-line help: a `Usage:` line, a wrapped prose description, and flat `Arguments:` / `Options:` / `Commands:` sections with no borders, wrapping naturally on a narrow terminal. That is the entire target. vaultspec-core must read the same way, for both help and data, end to end.

Three concrete defects compound the split. First, help is Rich-framed everywhere because not one of the seventeen `Typer` apps sets `rich_markup_mode`, so all inherit the panel default. Second, the next-step hint surface, although it has one accepted mechanism, is rendered in at least three hand-rolled forms (`Suggested Next Step:` with a `>` prefix from the shared helper, plus ad-hoc sync footers, status-rollup hints, and a migrations suggestion line), none of which matches the clean `Next action:` footer the reference tools use. Third, several data surfaces never adopted the standardization contract at all and still hand-format multi-column output: `vault stats`, `vault list`, `vault graph` metrics, the `vault repair` run report, both `status` modes (rollup and trace), `migrations status`, and `doctor` (which alone carries two divergent internal styles). Four separate glyph vocabularies coexist across these surfaces.

This ADR amends `cli-output-standardization` to bring Typer help into the contract, amends `cli-next-step-hints` to fix one rendered footer form, and finishes the migration the parent decision started so that no surface remains table-like.

## Considerations

- **The target is a fixed, observable artifact, not a taste.** `vaultspec-rag` and `glow` define the exact shape: plain `Usage`/`Arguments`/`Options`/`Commands` help and `Label: value` plus `Next action:` data. Conformance is checkable against those examples rather than argued.

- **Disabling Rich help is one setting, applied uniformly.** Typer reads `rich_markup_mode` per app instance; setting it to `None` makes Typer fall back to Click's standard `HelpFormatter`, which produces exactly the reference shape and wraps to the terminal width. There is no global switch, so every app must carry the setting. A single Typer factory that injects the setting (and the shared `no_args_is_help` defaults) is the one place to enforce it, so a new sub-app cannot silently reintroduce a panel.

- **Wrapping is wanted, fixed-width layout is not.** The parent ADR banned width-derived layout for byte-determinism. The user requirement that output wrap on small terminals is not in conflict with that: a renderer that lays out columns by terminal width is banned; a plain string line that the terminal soft-wraps is fine, and Click's help wrapping is the standard, expected behavior. The contract is therefore refined, not reversed: the renderer performs no width-derived layout; the terminal remains free to wrap long lines, and help uses Click's native wrapping.

- **Help examples belong in the reference, not the help string.** Plain Click collapses multi-line `help=` text into a single reflowed paragraph, mangling the root app's `Examples:` block into a run-on. The reference tools carry no inline examples in their top-level help for this reason. Examples move to the bundled CLI reference, which already exists as the durable home for worked invocations, keeping help strings to a one-line imperative summary plus a short wrapped description.

- **Hints already have a contract; only the rendered form is wrong.** `cli-next-step-hints` fixed the mechanism (a static verb-plus-outcome table, `--no-hints` / `VAULTSPEC_NO_HINTS` suppression, a JSON `next_step` field). This ADR keeps all of that and changes only the human rendering to one `Next action:` footer, then routes every ad-hoc hint through the same helper so the form cannot drift per command.

- **The data shapes already exist.** `render_record`, `render_listing`, `render_tree`, and `render_outcomes` are the proven four shapes. The unmigrated surfaces do not need new machinery; they need to stop hand-formatting and build one of the existing payloads.

## Constraints

- **Builds on shipped, in-tree parents.** This decision extends the mature `Outcome` taxonomy, the `json_envelope` shape, and the four rendering shapes, all in-repo and carrying no frontier risk. It must extend these, never fork them.

- **Rich remains a dependency, with a narrower role.** Rich still backs the data renderers' optional decorative color and the UTF-8 stdio hardening in `console.py`. Disabling `rich_markup_mode` removes Rich from the help path only. The library is not removed.

- **One-time help and footer text break is accepted.** Any tooling that scraped the framed help or the old `Suggested Next Step:` wording breaks once. Help text was never a machine contract, and `--json` carries the `next_step` field for machine consumers, so the break is cosmetic.

- **`--json` surfaces must not regress.** Every surface touched keeps or gains its canonical `--json` envelope; text changes never alter the machine contract.

- **No new technology.** This is a consolidation onto an existing internal pattern plus one documented Typer setting. The only risk is discipline, addressed by the factory and the contract tests below.

## Implementation

The work lands in four implementation phases plus tests, each independently shippable.

**Plain-Click help.** A small Typer factory becomes the single constructor for every app, injecting `rich_markup_mode=None` and the shared defaults. All seventeen apps adopt it. Help strings are normalized to one convention: a one-line imperative summary, sentence case, terminal period, with any longer description as a following wrapped sentence and no inline `Examples:` block. Option help strings are normalized the same way. The root app's examples move to the bundled CLI reference.

**One hint footer.** The shared hint helper is changed to emit a single `Next action:` footer with the suggested command indented on the following line, matching the reference tools. Every ad-hoc next-step surface (sync footers, status rollup and trace hints, the migrations suggestion) is rerouted through this helper or the static table, so one form governs all of them. The suppression flags and the JSON `next_step` field are unchanged.

**No table-like data surface.** Each unmigrated surface is converted to build a Record, Listing, or Tree payload and route through the shared emitter: `vault stats` and `vault graph` metrics become Records (with the per-type and per-feature breakdowns as Listings), `vault list` and `migrations status` become Listings, `vault repair` and both `status` modes become Trees or Listings with a summary line, and `doctor`'s two internal styles collapse onto the same shapes. The hand-formatted alignment, inline markup, and bypass paths are deleted at each call site.

**One glyph vocabulary.** The four divergent glyph sets collapse to the single ASCII status set already used by the outcome and dry-run renderers (`+ ~ - = * !`), so a reader learns one vocabulary. `console.py` is adjusted so output wraps naturally on a narrow terminal while the renderers continue to emit plain, width-independent strings.

**Tests and reference.** The existing no-box determinism test is extended to assert that no `--help` screen contains a panel border or box-drawing glyph, that help wraps under a narrow width, and that the hint footer renders in exactly one form. The bundled CLI reference is regenerated to host the relocated examples.

## Rationale

The least-invention path is to finish what `cli-output-standardization` started and to delete the one boundary it drew for a reason that no longer holds. That ADR kept Rich help because the contract governed data only; the user goal now explicitly puts help in scope, and the cost of conformance is a single documented Typer setting plus normalized strings. Pointing the whole CLI at two external, stable reference tools turns "make it look good" into a checkable target. Reusing the four existing shapes and the existing hint mechanism means no new abstractions: the remaining surfaces converge onto patterns the codebase already trusts, and the glyph and footer unification removes the last sources of per-command variation.

## Consequences

- **Gains.** Help and data read as one surface, both bog-standard and legible, both wrapping cleanly on a narrow terminal. A reader and a tool-harness learn one help shape, one data shape, one hint form, and one glyph set. The last hand-formatted surfaces lose their bespoke layout, closing the drift the parent ADR could not reach. Conformance becomes a passing or failing test against fixed references rather than a review opinion.

- **Costs, honestly.** It is a sweep across seventeen apps and roughly eight unmigrated surfaces plus their tests. Operators who liked the framed help boxes lose them; the mitigation is that the boxes carried no information and the plain form is the de-facto standard for command-line tools. Scrapers of old help or footer text break once; `--json` remains the contract.

- **Pitfalls.** The recurring risk is a future sub-app constructed with a bare `Typer(...)` call, silently restoring a panel, or a new command that hand-formats output. The mitigation is the shared factory as the only sanctioned constructor and the extended contract test that fails the build on a box-drawing glyph in help or data.

- **Pathways opened.** With help and data unified and width-independent, `console.py` can later shed remaining `safe_box` complexity, and new commands inherit the full presentation contract for free.
