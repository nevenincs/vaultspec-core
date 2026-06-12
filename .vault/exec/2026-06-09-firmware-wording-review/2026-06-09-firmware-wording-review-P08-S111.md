---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S111
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the host-specific read_file tool id with provider-neutral wording (D15)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-writer.md`

## Description

- Replace the host-specific tool identifier `read_file` in the Core Workflows audit
  bullet with the provider-neutral phrase "file reads"
- Format the persona with mdformat at wrap 88

## Outcome

The writer persona's audit workflow no longer names a single host's tool identifier,
per decision D15. The bullet now reads "using search tools or file reads", which holds
across every provider surface the firmware syncs to, matching the persona's own
provider-neutral Tooling Strategy bullet ("use the project's established search and
analysis tools"). Verification grep for the `read_file` token across the file returns
zero matches.

## Notes

None.
