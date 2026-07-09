# synthetic cli reference

This synthetic reference reproduces the structure of the generated command
inventory - section headings, backtick-wrapped invocations, inline backtick
flags, and wrapped continuation lines - with a handful of representative verbs.
It carries no personal data, usernames, or absolute paths.

<!-- vaultspec:generated:begin command-inventory -->

## Top-level commands

- `vaultspec-core status` - Orient in a vaultspec vault.
- `vaultspec-core sync` - Sync rules, skills, agents, configs, and MCPs.

## Vault

- `vaultspec-core vault list` - List vault documents, optionally filtered by
  `--feature` or its short form `-f`.
- `vaultspec-core vault add` - Create a new .vault/ document from a template.

### Check

- `vaultspec-core vault check all` - Run all vault health checks; with `--fix`,
  apply autofixes.
- `vaultspec-core vault check references` - Check for missing cross-references
  within features, honoring `--strict`.

### Plan

- `vaultspec-core vault plan step check` - Mark the Step closed (idempotent).
- `vaultspec-core vault plan tier demote` - Demote the plan tier; refuses a
  multi-child collapse without `--force`.

<!-- vaultspec:generated:end command-inventory -->

## Outside the markers

- `vaultspec-core should-not-appear` - This bullet sits outside the generated
  markers and must never enter the denominator.
