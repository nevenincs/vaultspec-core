---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S16
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# document vault feature archive --dry-run and --no-hints and add a vault feature unarchive prose section (D6)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Verify the live flag surfaces with `vault feature archive --help` and
  `vault feature unarchive --help` (read-only): archive lists `--dry-run` (preview
  planned changes), `--json`, and `--no-hints`; unarchive lists `--dry-run` and
  `--json` only, with no `--no-hints`
- Extend the archive prose section's option list from `--json` only to `--dry-run`,
  `--json`, and `--no-hints` (D6)
- Add a `vault feature unarchive` prose section in the archive section's
  one-sentence-plus-options style, noting explicitly that `--no-hints` is not
  accepted there
- Run mdformat --wrap 88 on the edited file

## Outcome

The bundled CLI reference now covers both halves of the feature lifecycle pair: archive
with its full live option set and the previously undocumented unarchive verb. The
archive-discipline and dry-run-discipline rules, shortened in P02 on the premise that
archive `--dry-run` and the paired unarchive verb exist, now resolve against the
bundled reference instead of only against live `--help`.

## Notes

The `--no-hints` asymmetry between archive and unarchive is a live-CLI fact, recorded
as-is rather than papered over. The new prose retains the section's existing em-dash
connector for style consistency; P08.S92 sweeps em dashes across this file later.
