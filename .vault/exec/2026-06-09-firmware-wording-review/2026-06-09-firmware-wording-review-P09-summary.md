---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P09` summary

Phase P09 (propagation and verification) closed the final six Steps S121-S126,
implementing ADR decision D16 and discharging the plan's Verification contract. Source
edits were propagated to the deployed mirror, the rename-driven downstream-upgrade hazard
(REVIEW-005) was remediated in real Python rather than logged, the residual British
spellings the audit named were fixed, the CLI-reference drift guard was extended, and
every health gate (vault check, spec doctor, full test suite, prek hooks) reports green.
With S121-S126 closed all 126 plan rows are now complete.

- Modified: `src/vaultspec_core/vaultcore/hydration.py`,
  `src/vaultspec_core/vaultcore/tests/test_hydration.py`,
  `src/vaultspec_core/tests/cli/test_cli_reference_drift.py`, `docs/CLI.md`,
  `docs/framework.md`,
  `.vault/audit/2026-06-10-firmware-wording-review-audit.md` (REVIEW-005 flipped to
  resolved)
- Refreshed (gitignored, not committed): the deployed `.vaultspec/rules/` mirror via
  `install --upgrade`, including the manual deletion of the stale generated orphan
  `templates/ref-audit.md`
- Created: six Step Records `...-P09-S121.md` through `...-P09-S126.md` and this summary

## Description

Each Step landed as one commit carrying its work, its Step Record, and the CLI-driven
plan-state change; every pre-commit hook passed on every commit. Commit hashes:
S121 `52fe005`, S122 `c68ebfc`, S126 `38da3f4`, S123 `4e4855e`, S124 `faf19a1`,
S125 `4dfef76`.

A propagation-pipeline dependency was discovered and is the one operational subtlety of
the phase. `sync` regenerates the provider mirrors from the deployed `.vaultspec/rules/`
intermediate, not directly from `src/vaultspec_core/builtins/`; and `install --upgrade`
refreshes that intermediate from the source builtins. The deployed mirror was stale at
phase start (it still shipped `ref-audit.md` and pre-P01 content), so the S122 upgrade had
to be applied before the S121 sync could carry the corrected source to the provider
surfaces. The two Steps are recorded in plan row order but the upgrade necessarily ran
first in execution time; both records state this. A second discovery: all four provider
mirror trees (`.claude/`, `.agents/`, `.codex/`, `.gemini/`) and the entire `.vaultspec/`
tree are gitignored in this repository, so neither the sync nor the upgrade produces any
tracked git change. The S121-S124 commits are therefore documentation-only.

S121 (D16, sync): `vaultspec-core sync` completed aggregate `unchanged` - 94 items, all
`unchanged` (claude 29, gemini 29, codex 18, antigravity 17, mcps 1), zero failed. The
phantom plan-skill name `vaultspec-write-plan` is absent from every regenerated mirror.

S122 (D16, upgrade): `vaultspec-core install --upgrade` completed `1 created 40 updated 8 unchanged`, zero failed. The created entry is `templates/reference.md`. The upgrade does
not prune retired files, so it left the stale `templates/ref-audit.md` in place; that one
orphan was deleted by hand, leaving the mirror's template set correct (`reference.md`
present, `ref-audit.md` absent).

S126 (D16, REVIEW-005, real Python): `get_template_path` in `hydration.py` gained a
data-driven legacy-filename fallback (`_LEGACY_TEMPLATE_NAMES`,
`DocType.REFERENCE -> ref-audit.md`). When the renamed `reference.md` is absent the
resolver returns the legacy `ref-audit.md` if present and warns, naming
`vaultspec-core install --upgrade`; when neither exists, `create_vault_doc` raises a
`FileNotFoundError` whose message names the same remedy. Five real, non-tautological unit
tests in `test_hydration.py` cover current-name preference, legacy fallback (with warning
assertion), both-missing `None`, end-to-end scaffolding from the legacy template, and the
actionable error. The targeted suite reports 21 passed; `vault add reference --dry-run`
resolves without "No template found"; REVIEW-005 was flipped to resolved with evidence.
The tier-enum code-binding check (P05.S34) verdict was UNBOUND - the persona `tier:` value
is never parsed as an enum in any Python loader or test - so no separate enum follow-up
exists or was created.

S123 (D16, health): `vault check all` green (eleven checkers clean) and `spec doctor`
green (every component ok); `install --upgrade --dry-run` previews `49 unchanged` (zero
pending).

S124 (D16, tests): full suite `2041 passed in 309.49s`, exit 0; `prek run --all-files`
all hooks passed.

S125 (D16, right-sized deferral): the deferred "automate cli.md regeneration" item was
right-sized rather than logged. Four residual British spellings in `docs/CLI.md` and
`docs/framework.md` were Americanized (`Synthesised`, `synthesised`, `serialise`,
`customisation`), formatted with `mdformat --wrap 88` per the docs hook. The existing
comprehensive drift guard `test_cli_reference_drift.py` (walks the live Typer tree and
asserts every command and non-global option appears in the bundled reference) was extended
with `test_p03_surfaced_tokens_are_in_reference`, pinning the specific P03 tokens
(`--tier`, `--step`, `--all-steps`, `--no-hints`, `--dry-run`, `--phase`, `--wave`,
`--canonicalise`, `rename-integrity`, `unarchive`); 4 passed. The full Typer-surface
auto-generator is documented as a non-blocking future enhancement: a hand-authored
reference plus an enforced drift guard delivers the same no-silent-drift guarantee without
the generator's maintenance burden.

## Feature verification

The plan's Verification section was re-run at phase close; every bullet passes.

- Phantom skill name: `grep -rl "vaultspec-write-plan" src/vaultspec_core/builtins/`
  returns zero; the same search across `docs/` and `src/` returns zero outside historical
  `.vault/` documents (D1).
- Em dashes: `grep -rl` for the em-dash character across
  `src/vaultspec_core/builtins/` returns zero (D15).
- Literal tag example: `grep -rn "'#feature'"` across the builtins returns zero; the
  convention placeholder `'#{feature}'` is used throughout (D15, REVIEW-003).
- Inventory British spellings: a grep for the research inventory's British forms
  (serialiser, behaviour, centre, authoris\*, parallelis\*, summaris\*, synthesis\*,
  customis\*, and the rest) across the builtins returns zero (D15, REVIEW-006).
- Plan rows: all 126 rows are closed (`- [x]`), zero open (`- [ ]`); the closed-row count
  is 126.
- Plan checker: `vaultspec-core vault plan check` on the plan exits 0 with no violations.
- Propagation: `vaultspec-core sync` reports zero failed (94 unchanged) and
  `vaultspec-core install --upgrade --dry-run` previews zero pending (49 unchanged) (D16).
- Health: `vaultspec-core vault check all` and `vaultspec-core spec doctor` both exit
  green (D16).
- Tests: the full suite reports 2041 passed, exit 0; `prek run --all-files` passes (D16).
- Follow-up items: the two deferred items were remediated in code per the user's
  override rather than logged - the template-filename hazard in S126 and the
  cli-reference drift in S125 - and the tier-enum check surfaced no Python work (D16).

## Notes

The new Python introduced in this phase (the S126 resolver fallback plus its five tests,
and the S125 drift-guard test) is in scope for orchestrator re-review before final
feature sign-off; the mandatory `vaultspec-code-reviewer` gate on the completed change set
has not yet run. Per the user's explicit direction, no `gh issue create` was invoked for
either deferred item; both were remediated in place.
