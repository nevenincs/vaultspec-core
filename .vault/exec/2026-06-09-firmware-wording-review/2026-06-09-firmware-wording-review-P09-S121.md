---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S121
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# run vaultspec-core sync to propagate the source edits to every provider surface (D16)

## Scope

- `src/vaultspec_core/builtins`

## Description

- Previewed propagation with `vaultspec-core sync --dry-run`, then applied
  `vaultspec-core sync` to regenerate every provider mirror
- Grepped the regenerated provider mirrors for the retired phantom skill name
  `vaultspec-write-plan`
- Recorded the sync outcome vocabulary tally

## Outcome

`vaultspec-core sync` completed with aggregate status `unchanged`: 94 items, all
`unchanged` (claude 29, gemini 29, codex 18, antigravity 17, mcps 1), zero `failed`,
`created`, `updated`, `removed`, `restored`, or `skipped`. Decision D16's propagation is
discharged.

Two propagation facts were verified and are load-bearing for the rest of P09:

- `sync` regenerates the provider mirrors from the deployed `.vaultspec/rules/`
  intermediate, not directly from `src/vaultspec_core/builtins/`. Because the deployed
  mirror was stale at the start of the phase (it still shipped `ref-audit.md` and the
  pre-P01 phantom name), the `install --upgrade` of S122 had to refresh `.vaultspec/`
  before this `sync` could see the corrected source. The upgrade was therefore applied
  first in execution order even though it is recorded under S122; this is the only safe
  ordering and is noted here so the trail is honest.
- All four provider mirror trees (`.claude/`, `.agents/`, `.codex/`, `.gemini/`) are
  fully gitignored in this repository: `git ls-files` reports zero tracked files under
  them and `git check-ignore` confirms each is ignored. The S121 task contract to
  "stage every tracked regenerated provider artifact" therefore resolves to zero tracked
  artifacts; there is nothing to add to the index. The mirrors are regenerated workspace
  output, reconstructed on demand by `sync`, not committed source.

Verification: a recursive grep for `vaultspec-write-plan` across `.claude/`, `.agents/`,
`.codex/`, and `.gemini/` returns zero matches. The phantom plan-skill name retired in
P01 is absent from every regenerated provider surface.

## Notes

No tracked git changes result from this Step because the provider mirrors are gitignored
by design. The S121 commit is therefore a documentation-only commit carrying this Step
Record and the plan-row closure. The sync-after-upgrade ordering dependency is the one
operational subtlety; it is recorded above and again in the S122 record.
