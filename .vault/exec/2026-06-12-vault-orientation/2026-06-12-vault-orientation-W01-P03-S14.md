---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S14
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# refresh the modified stamp on every plan serialization write

## Scope

- `src/vaultspec_core/vaultcore/models.py`
- `src/vaultspec_core/vaultcore/__init__.py`
- `src/vaultspec_core/cli/plan_cmd.py`

## Description

- Add the shared `refresh_modified_stamp(text, today)` helper to `src/vaultspec_core/vaultcore/models.py`. It operates on full document text, rewrites an existing frontmatter `modified:` value to today in canonical quoted `yyyy-mm-dd` form preserving the field's indentation and line ending, or inserts the field directly after the `date:` anchor when absent, and returns the input unchanged when there is no frontmatter fence or no `date:`/`modified:` anchor. Only the leading frontmatter block is touched; body occurrences are never rewritten.
- Re-export `refresh_modified_stamp` from the `vaultspec_core.vaultcore` package in `src/vaultspec_core/vaultcore/__init__.py` so every mutation path imports it from one place.
- Wire the helper into the single plan-write choke point `_save_plan_or_dry_run` in `src/vaultspec_core/cli/plan_cmd.py`. The refresh is applied to the serialised text immediately after `serialise_plan`, so it runs before the unified-diff preview is built (keeping a dry-run preview truthful by showing the stamp change) and before the on-disk write.

## Outcome

Every plan structural and state mutation that flows through serialization now refreshes the plan's `modified:` stamp to today. Because the plan serializer renders canonical frontmatter and does not itself emit `modified:`, the helper is what re-establishes the field on every write, refreshing it when present and adding it after `date:` on a stamp-less plan. A pure `--dry-run` writes nothing but its diff preview includes the stamp change. Targeted plan and vaultcore suites pass (642 tests); ruff format, ruff check, and ty all clean.

## Notes

The plan serializer was already the documented choke point for all plan mutations (step add/check, phase/wave ops, tier ops). The retirement-guard re-parse and the growth-ceiling guard in the choke point both operate on the stamped text without issue, since the stamp is structurally invisible to plan parsing. No `modified:` handling was added to `src/vaultspec_core/plan/frontmatter.py`: the choke point owns the refresh and the serializer's canonical frontmatter render is left untouched.
