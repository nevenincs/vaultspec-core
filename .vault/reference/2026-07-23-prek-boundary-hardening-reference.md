---
tags:
  - '#reference'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - "[[2026-07-23-prek-boundary-hardening-adr]]"
  - "[[2026-07-23-prek-boundary-hardening-plan]]"
---

# `prek-boundary-hardening` reference: `verified prek contract`

Empirical verification of the two prek behaviors the boundary hardening rests on,
performed against a live prek release (prek 0.4.10, build b45e67100, 2026-07-16,
invoked through uvx) in throwaway git repositories. Both previously-unverified
assumptions from the research are now confirmed observations.

## Summary

### Config-discovery precedence: prek.toml wins silently

With only `prek.toml` present, `prek list` resolves hooks from it. With both
`prek.toml` and `.pre-commit-config.yaml` present in the same root, `prek list`
resolves hooks exclusively from `prek.toml`: a local hook defined only in the YAML
does not appear, prek emits no warning and no error, and the exit code is 0. The
embedded assumption "prek reads `prek.toml` exclusively" holds, with the refinement
that the co-present YAML is silently ignored rather than rejected. Consequence for
the lifecycle decision: a superseded `.pre-commit-config.yaml` is untidy (stale,
misleading to humans and to pre-commit proper) but not breaking to prek, so
operator-gated advisory cleanup is sufficient and automatic deletion is not
required for correctness.

### Local system hook TOML schema

`prek sample-config --format toml` emits `[[repos]]` array-of-tables with a `hooks`
array. `prek validate-config` accepts, and `prek list` resolves, the full vaultspec
canonical hook shape rendered as nested array-of-tables:

- `[[repos]]` with `repo = "local"`
- `[[repos.hooks]]` per hook carrying `id`, `name`, `entry`, `language = "system"`,
  `pass_filenames = false`, and the per-hook filter field: `types = ["markdown"]`
  and `always_run = true` were both validated verbatim.

The sample config carries an optional schema pragma comment pointing at
`https://www.schemastore.org/prek.json`.

### Managed-block rendering is viable

Because the hook set renders as a self-contained run of `[[repos]]` /
`[[repos.hooks]]` array-of-tables, it is expressible as a delimited text block
appended at end of file without parsing or rewriting operator-authored TOML:
appending array-of-tables headers at EOF is valid TOML and validated clean. No
round-trip TOML writer is needed; `tomllib` remains sufficient for the read side
(the boundary predicate's content check).

### Verification transcript shape

Probes executed: `prek --version`; `prek sample-config --format toml`;
`prek validate-config prek.toml` plus `prek list` in a repo with only `prek.toml`
carrying a local system hook; the same after adding a `.pre-commit-config.yaml`
with a distinct local hook (YAML hook absent from `prek list`, no diagnostics,
exit 0); `prek validate-config` plus `prek list` over a two-hook `prek.toml` using
the exact vaultspec field set including `types` and `always_run`.
