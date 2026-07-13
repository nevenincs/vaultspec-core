---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P03` summary

Phase P03 (bundled CLI reference update) closed all five Steps S15-S19, implementing
ADR decision D6: the machine-facing CLI reference is hand-updated to the live 0.1.26
surface, closing the five lag items the research identified, so sibling rules no
longer depend on undocumented flags.

- Modified: `src/vaultspec_core/builtins/reference/cli.md`
- Created: five Step Records `...-P03-S15.md` through `...-P03-S19.md` in this folder

## Description

S15 (vault add flags): four rows appended to the `vault add` options table, mirroring
the live `--help` order: `--no-hints`, `--tier TIER` (default `L1`, ignored for
non-plan document types), `--step ID` (canonical ID or display path of the Step to
scaffold), and `--all-steps`. Defaults and descriptions were derived from the help
output.

S16 (feature lifecycle pair): the archive prose section's option list grew from
`--json` only to `--dry-run`, `--json`, and `--no-hints`, and a new
`vault feature unarchive` prose section was added in the same one-sentence-plus-options
style. The live asymmetry that unarchive accepts no `--no-hints` is recorded as-is.

S17 (checker list): `rename-integrity` appended to the `vault check` prose subcommand
list with a one-sentence description from the help text, bringing the prose section
back into agreement with the command inventory block, which already listed the verb.

S18 (plan verbs): a standalone sentence now states that every mutating plan verb
accepts `--dry-run` and `--canonicalise` (off by default, preserving authored prose);
`--phase` (parent Phase id, required at L2+, omitted at L1) joined the Step `add`
prose and `--wave` (parent Wave id, L3+ only) joined the Phase `add` prose.
Universality was confirmed against `step add`, `phase add`, `wave add`,
`tier promote`, `step check`, `epic intent edit`, and `tier demote` help output.

S19 (sync vocabulary): a "Sync output vocabulary" section after the sync command
section documents the shared outcome vocabulary (`created`, `updated`, `unchanged`,
`removed`, `restored`, `skipped`, `failed`), its semantics (`unchanged` is a
successful no-op; `skipped` always carries a reason; only `failed` stops the
pipeline), and the `--json` aggregate (`vaultspec.sync.v1` schema, top-level `status`,
`mixed` when items disagree), matching the wording the research verified accurate in
the CLI rule.

Every addition was grounded in read-only `--help` invocations; no mutating command ran
during verification. Each Step landed as one commit carrying the edit, its Step
Record, and the CLI-driven plan-state change; all pre-commit hooks pass on every
commit. One out-of-scope discovery is logged in the S18 record for the P09.S125
regeneration follow-up: `vault plan tier promote` also exposes an undocumented
`--target TIER` option. The em-dash connectors in the feature-archive section were
retained for local style consistency; P08.S92 sweeps em dashes across this file.
