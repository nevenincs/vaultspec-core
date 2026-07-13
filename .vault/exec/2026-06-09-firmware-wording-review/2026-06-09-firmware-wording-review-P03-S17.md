---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S17
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# append rename-integrity to the vault check prose checker list (D6)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Verify with `vault check --help` (read-only) that `rename-integrity` is a live
  subcommand described as "Check name/filename integrity for rules, skills, and
  agents"
- Append `rename-integrity` to the prose subcommand list in the `vault check` section
  and add a one-sentence description derived from the help text (D6)
- Run mdformat --wrap 88 on the edited file

## Outcome

The `vault check` prose section now enumerates all twelve live subcommands; the command
inventory block already listed `vault check rename-integrity`, so the inventory and the
prose section agree again. This closes the third `reference/cli.md` lag item from the
research (the prose checker list omitting `rename-integrity`).

## Notes

None. The existing prose list order (which differs from the `--help` display order) was
preserved; `rename-integrity` was appended at the end, matching its position in the
live help.
