---
tags:
  - '#research'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
related:
  - '[[2026-05-15-operator-cli-repair-pipeline-reference]]'
---



# `operator-cli-repair-pipeline` research: `repair pipeline design`

Research for redesigning the vault-content repair workflow after direct
operator feedback. Scope covers current CLI behavior, generated feature-index
lifecycle, path/case handling, output design, and recovery automation.

## Findings

### Current implementation facts

`vaultspec-core vault check all` runs the check suite through `run_all_checks`
in this order:

1. `structure`
1. `frontmatter`
1. `links`
1. `dangling`
1. `body-links`
1. `orphans`
1. `features`
1. `references`
1. `schema`

The implementation builds one graph and one snapshot before dispatching the
checks. Mutating checkers can therefore change files while later checks still
hold pre-fix graph state. This is the code-level explanation for the
operator-facing "half-fixed, rerun, new class of issue appears" experience.

In this worktree, `uv sync --all-extras --dev` completed successfully,
`vaultspec-core --help` ran, `vaultspec-core spec doctor --json` reported the
framework present and current, and `vaultspec-core vault check all --json`
exited successfully. The only existing findings were two INFO-level feature
research gaps for other features.

`vaultspec-core vault check all --fix` is a partial fixer. It passes mutation
through to structure, frontmatter, links, dangling, references, and schema.
`body-links`, `orphans`, and `features` remain diagnostic-only.

`vaultspec-core vault feature index` is the only current index rebuild surface.
It writes generated `.vault/index/<feature>.index.md` files with
`generated: true`, `#index`, and one feature tag. It supports JSON output but
has no dry-run mode and no integrated post-repair guidance.

Lazy migrations run through the vault scan path, so many
`vaultspec-core vault ...` commands can apply schema migration work before
performing their apparent primary command. The current workspace migration
status is `up_to_date`.

### External design anchors

CLI Guidelines emphasizes human-first CLI design, machine-readable JSON, brief
success output, and explicit state-change reporting. Source:
https://clig.dev/

Microsoft System.CommandLine design guidance says command groups should group
subcommands, options should parameterize command behavior, and CLI contracts
are difficult to change once users script them. Source:
https://learn.microsoft.com/en-us/dotnet/standard/commandline/design-guidance

Microsoft Windows file naming guidance says developers should not assume case
sensitivity; NTFS supports POSIX case sensitivity, but that is not the default
behavior. Source:
https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file

Azure Repos cross-platform Git guidance states that Windows and macOS are
case-insensitive but case-preserving by default, while Git is case-sensitive.
It recommends avoiding case conflicts and enforcing exact capitalization.
Source:
https://learn.microsoft.com/azure/devops/repos/git/os-compatibility

Google SRE emergency-response guidance highlights recovery automation with
sanity checks, documented failure modes, and follow-up hardening. Source:
https://sre.google/sre-book/emergency-response/

### Local documentation context

Older `vault-doctor-suite` documents are useful precedent but are historical.
They refer to older package paths and a proposed doctor surface that does not
match the current `vaultspec-core vault check` plus
`vaultspec-core spec doctor` split.

The index-folder and migration-registry history matters. Older index-folder
material expected `vaultspec-core vault check --fix` to relocate indexes.
Newer migration-registry material moves relocation to migrations and lazy
first-use behavior. The repair design should preserve that newer boundary:
migrations own schema relocation; structure fixing must not relocate generated
indexes.
