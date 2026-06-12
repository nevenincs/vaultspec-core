---
tags:
  - '#audit'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# `cli-reference-automation` audit: `cli reference generator code review`

## Scope

Mandatory review gate on the CLI-reference auto-generator built in P02.S05/S06
(commits `8748cf7`, `9e8d53a`, `c2b597f`): the `vaultspec-core spec reference generate`
verb with `--check`, the managed/unmanaged-region scheme in
`src/vaultspec_core/builtins/reference/cli.md`, the `cli-reference-check` pre-commit
hook, and the new test suite `test_cli_reference_generated.py`. One reviewer covered
correctness, region-scheme safety, the visible-verb departure from the ADR, test
quality, and maintainability.

## Findings

### Verdict: sign-off (no critical, high, or medium findings)

The generator walks the live Typer tree correctly (107 signatures, prior hand-authored
omissions now covered), fails loud on absent markers, preserves prose byte-for-byte, is
idempotent, writes with `newline="\n"` so Windows CRLF cannot leak, and is covered by
ten real non-tautological tests. All verification commands green: 14 targeted tests
pass, `spec reference generate --check` exits 0, ruff and ty clean. The visible-verb
departure is sound and required (the language-contract guard rejects documented-but-
hidden commands).

### LOW

- `GENREVIEW-001` | LOW | resolved - reversed markers (end before begin) raise
  "Missing end marker", naming the wrong defect. `src/vaultspec_core/cli/reference_gen.py`
  `replace_managed_region`: the end search is anchored after the begin index, so a
  misordered pair reports a missing end marker that is actually present. Fix: detect the
  unanchored-end-found-but-anchored-failed case and raise a distinct "end marker precedes
  begin marker" message. **Resolved:** `_replace_region` now raises
  `ReferenceMarkerError("End marker precedes begin marker for region '<id>'")` when the
  anchored end search fails but an unanchored one succeeds;
  `test_reversed_markers_raise_distinct_message` proves the distinct message.
- `GENREVIEW-002` | LOW | resolved - duplicated begin markers silently swallow the first
  region's body (the one silent-corruption path in an otherwise fail-loud design).
  `src/vaultspec_core/cli/reference_gen.py`: assert each region's begin and end marker
  count is exactly one before replacing; raise `ReferenceMarkerError` on a duplicate.
  **Resolved:** `_replace_region` now counts each marker and raises
  `ReferenceMarkerError("Duplicate begin/end marker for region '<id>' ...")` before any
  replacement; `test_duplicate_begin_marker_raises` proves the raise and that the first
  body is no longer swallowed.
- `GENREVIEW-003` | LOW | resolved - `docs/CLI.md`'s parallel command inventory is not
  generator-owned and has already drifted in ordering from `cli.md` (first divergence at
  index 7, `vault repair` vs `vault graph`). The ADR's Problem Statement names the
  two-surface burden as the motivation; automating only one surface leaves the second to
  drift. Fix: make the `docs/CLI.md` inventory block a second managed region owned by the
  same generator (the `MANAGED_REGIONS` registry was built to extend to additional files
  and regions), so `--check` covers both surfaces. **Resolved (managed-region path):**
  `docs/CLI.md`'s inventory was confirmed to be the same `text` signature-block format
  the generator emits, so its prior bespoke `vaultspec-cli-signatures:start/end` markers
  were replaced with the canonical `vaultspec:generated:begin/end command-inventory`
  markers and the generator now owns it. The registry generalized to a `MANAGED_FILES`
  tuple of `ManagedFile(path_factory, regions, optional)` entries; the bundled reference
  and the handbook share the `command-inventory` region, so they are sourced from one
  Typer walk and cannot diverge. Regenerating reconciled the handbook to the live tree
  (added the missing `vault graph`, fixed the index-7 ordering and the
  `rule promote`/`adr supersede` and `*-restore`/`*-sync` orderings); every hand-written
  handbook sentence outside the markers is preserved verbatim. `generate_all` drives the
  verb and `--check` over both files; the `cli-reference-check` pre-commit hook scope now
  includes `docs/CLI.md`. The source-only handbook is `optional=True` so an installed
  wheel that does not ship it is skipped rather than failing. New tests:
  `test_registry_owns_both_surfaces_with_shared_region`,
  `test_generate_all_check_covers_both_files_in_sync`,
  `test_check_mode_via_cli_reports_both_files`,
  `test_handbook_inventory_equals_live_tree_set_and_order`,
  `test_corrupted_handbook_region_is_detected`, and
  `test_handbook_prose_outside_region_survives_regenerate`.
- `GENREVIEW-004` | LOW | resolved (accepted as-is) - `generate` write-mode resolves the
  package path, which under a non-editable installed wheel would be read-only. The verb
  is a developer/CI tool and degrades to a clean exit-1 with a remedy-naming message via
  the `OSError` catch; no traceback. Accepted: the dev/CI workflow the ADR targets is
  correct, and the error path is graceful.

## Recommendations

- Remediate `GENREVIEW-001`, `GENREVIEW-002`, and `GENREVIEW-003` in place per the
  "nothing deferred" directive, then re-run `spec reference generate --check`, the
  generator test suite, the drift guard, and the full suite plus prek.
- `GENREVIEW-003` fulfills the ADR's two-surface motivation directly; after it lands,
  `docs/CLI.md` and `cli.md` inventories cannot silently diverge.

## Remediation

All three actionable findings are remediated in-cycle (one commit each, code plus test
plus this status flip). `GENREVIEW-001` and `GENREVIEW-002` harden the marker-handling in
`reference_gen.py` (distinct reversed-marker error; exactly-once marker guard).
`GENREVIEW-003` takes the managed-region path: `docs/CLI.md`'s inventory was the same
signature-block format the generator emits, so it is now a second generator-owned file in
the `MANAGED_FILES` registry sharing the `command-inventory` region with `cli.md`, and
`spec reference generate --check` plus the `cli-reference-check` pre-commit hook cover
both surfaces. `GENREVIEW-004` was accepted as-is. `spec reference generate --check` exits
0 over both files; the generator test suite and both drift guards pass.

## Codification candidates

- **Source:** the generator design and `GENREVIEW-002`/`GENREVIEW-003`.
  **Rule slug:** `generated-reference-is-cli-owned`.
  **Status:** promoted - codified as the `generated-reference-is-cli-owned` builtin rule
  (`src/vaultspec_core/builtins/rules/generated-reference-is-cli-owned.builtin.md`).
  **Rule:** The bundled CLI reference's generator-managed regions are updated only by
  running `vaultspec-core spec reference generate`, never by hand-editing inside the
  managed markers; `--check` gates CI and fails until the reference matches fresh output.
  (Already named as a candidate in the cli-reference-automation ADR; promote after the
  generator surface stabilizes across both managed files.)
