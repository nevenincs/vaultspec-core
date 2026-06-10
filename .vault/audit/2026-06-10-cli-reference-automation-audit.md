---
tags:
  - '#audit'
  - '#cli-reference-automation'
date: '2026-06-10'
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

- `GENREVIEW-001` | LOW | open - reversed markers (end before begin) raise
  "Missing end marker", naming the wrong defect. `src/vaultspec_core/cli/reference_gen.py`
  `replace_managed_region`: the end search is anchored after the begin index, so a
  misordered pair reports a missing end marker that is actually present. Fix: detect the
  unanchored-end-found-but-anchored-failed case and raise a distinct "end marker precedes
  begin marker" message.
- `GENREVIEW-002` | LOW | open - duplicated begin markers silently swallow the first
  region's body (the one silent-corruption path in an otherwise fail-loud design).
  `src/vaultspec_core/cli/reference_gen.py`: assert each region's begin and end marker
  count is exactly one before replacing; raise `ReferenceMarkerError` on a duplicate.
- `GENREVIEW-003` | LOW | open - `docs/CLI.md`'s parallel command inventory is not
  generator-owned and has already drifted in ordering from `cli.md` (first divergence at
  index 7, `vault repair` vs `vault graph`). The ADR's Problem Statement names the
  two-surface burden as the motivation; automating only one surface leaves the second to
  drift. Fix: make the `docs/CLI.md` inventory block a second managed region owned by the
  same generator (the `MANAGED_REGIONS` registry was built to extend to additional files
  and regions), so `--check` covers both surfaces.
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

## Codification candidates

- **Source:** the generator design and `GENREVIEW-002`/`GENREVIEW-003`.
  **Rule slug:** `generated-reference-is-cli-owned`.
  **Rule:** The bundled CLI reference's generator-managed regions are updated only by
  running `vaultspec-core spec reference generate`, never by hand-editing inside the
  managed markers; `--check` gates CI and fails until the reference matches fresh output.
  (Already named as a candidate in the cli-reference-automation ADR; promote after the
  generator surface stabilizes across both managed files.)
