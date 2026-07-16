---
tags:
  - '#research'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-firmware-code-boundary-adr]]"
  - '[[2026-07-16-firmware-code-boundary-research]]'
---

# `code-boundary-check` research: `check-engine grounding for the source-boundary scanner`

The question (GitHub issue 213, the follow-up the firmware-code-boundary decision
registered): how a read-only scanner that sweeps source-file content for references to
the project's own vault records fits the existing check engine. The boundary premise
and design constraints are recorded in the related firmware-code-boundary documents
and are not restated here; this research grounds the engine mechanics. The evidence
picture: the check engine has a clean per-checker module pattern with a shared result
model, warnings do not affect exit codes (advisory is the default posture), `check all` is strictly vault-scoped and snapshot-driven, and standalone check verbs outside
`run_all_checks` are an established shape.

## Findings

### The checker contract is one module returning a CheckResult

Each checker is a module under `src/vaultspec_core/vaultcore/checks/` returning
`CheckResult` with `CheckDiagnostic` entries carrying `Severity.ERROR/WARNING/INFO`,
`fixable`, and `fix_description` (`checks/_base.py:38-102`). Rendering is shared
(`_base.py:175`), ASCII-only per the presentation-uniformity decision.

### Warnings are advisory by construction

The CLI exits 1 only on ERROR-severity findings; warnings render and exit 0
(`src/vaultspec_core/cli/vault_cmd.py:1060-1085`, both JSON and console paths). A
warnings-only checker is therefore advisory with no extra machinery, satisfying the
report-never-block constraint the governing decision set.

### check all is vault-scoped and snapshot-driven; membership is explicit

`run_all_checks` builds one `VaultGraph` snapshot of `.vault/` documents and passes it
to seventeen checkers in a hardcoded order (`checks/__init__.py:72-121`); every
current checker reads vault documents, none walks the source tree. Including a
repo-walking scanner would change `check all`'s cost profile and scope; excluding it
means a checker is reachable only through its own verb - a shape that already exists
(`vault check adr-status` is registered as its own subcommand at
`cli/vault_cmd.py:1770` in addition to membership, and `vault plan check` lives
entirely outside `run_all_checks`).

### Record stems are enumerable and distinctive

Every authored record's stem embeds the `yyyy-mm-dd-` date prefix, and generated
indexes end `.index.md` (`checks/_base.py:105-138`); the stem population is
enumerable by listing `.vault/` (the graph keys nodes by stem, per the stem-collision
guard in `vaultcore/hydration.py:446-459`). Stems are therefore high-precision scan
needles; bare Step ids (`S01`) or the literal `.vault` string would be
false-positive-prone in vault-domain codebases, as the governing decision's
self-hosting constraint anticipates.

### Scan-set mechanics

No existing core code walks the project source tree for content (checks read
`.vault/` only; sync walks `.vaultspec/` and provider dirs). A scanner needs its own
walk with exclusions (`.vault/`, `.vaultspec/`, provider directories, `.git`,
caches), a text-decode guard, and a size cap; provider directory names are already
enumerated centrally (`core/enums.py` `DirName`, consumed in
`core/gitignore.py:110-155`). Pure-offline operation (no git dependency) follows the
commit-linkage decision's precedent of validation as a pure string operation.

### Not investigated

Scan performance on very large source trees was not measured; the walk cost is
bounded by the same exclusions plus the size cap, and the opt-in posture makes cost a
caller decision. Whether downstream repos want a pre-commit hook entry for the
scanner is deferred with the adoption question.

## Sources

- `src/vaultspec_core/vaultcore/checks/_base.py:38-138`
- `src/vaultspec_core/vaultcore/checks/_base.py:175`
- `src/vaultspec_core/vaultcore/checks/__init__.py:72-121`
- `src/vaultspec_core/cli/vault_cmd.py:1060-1085`
- `src/vaultspec_core/cli/vault_cmd.py:1770`
- `src/vaultspec_core/vaultcore/hydration.py:446-459`
- `src/vaultspec_core/core/gitignore.py:110-155`
- https://github.com/nevenincs/vaultspec-core/issues/213
