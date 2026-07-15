---
tags:
  - '#audit'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# `provider-mcp-enrollment` audit: `provider-native enrollment release review`

## Scope

This audit reviews the complete provider-native MCP enrollment feature against its accepted ADR and implementation plan. It covers typed provider and scope resolution, Claude and Antigravity JSON reconciliation, Codex TOML reconciliation, external ownership state, legacy marker migration, force adoption, prune and selective uninstall, install and sync lifecycle integration, CLI and gateway mutation boundaries, companion package launch rendering, operator guidance, and real Claude Code and Codex CLI acceptance.

## Findings

### install-syncresult-success | high | resolved: install reported success after native-store reconciliation errors

The release review confirmed that the inherited install orchestration consumed MCP `SyncResult` items but did not inspect its errors. A malformed provider-native store could therefore prevent enrollment while the API returned an install result and the CLI exited successfully. The fix adds a single reconciliation-success boundary used by fresh install, fresh preview, upgrade preview, actual upgrade, and targeted mode migration. Any detailed or count-only reconciliation error now becomes a typed `VaultSpecError`, which the CLI renders with a non-zero exit. Real-file API and CLI regressions use a malformed Claude `.mcp.json` and prove that neither surface claims success.

### claude-local-windows-key | medium | resolved: Windows path spelling did not match Claude's local project key

Real Claude Code acceptance found that local enrollment used a backslash-form absolute path under `~/.claude.json`, while Claude keys the projects object with the forward-slash absolute spelling on Windows. The writer and empty-container cleanup now use the same resolved POSIX path form. Claude Code 2.1.210 recognizes the resulting local entry.

### host-trust-and-approval | low | accepted: enrollment does not grant provider runtime authority

Claude project enrollment is visible to the host while remaining pending until the host's approval flow completes. Codex project recognition requires its native project trust/config behavior. Status therefore remains configuration- and ownership-only and does not infer process health, approval, or connectivity. The CLI and operator guide state that boundary explicitly.

### repository-wide-collection-layout | low | non-blocking pre-existing test-layout conflict

The repository's CI-defined unit target is green. An additional all-roots collection attempt remains blocked independently of this feature by duplicate `test_normalize.py` module names under the default import mode; switching to importlib mode reaches an unrelated optional `statistic` package import. The feature's focused root suites and installed-host acceptance were run separately and are green.

## Recommendations

- Preserve the reconciliation-success boundary for any future install-time resource adapter; install must not turn an error-bearing `SyncResult` into success.
- Keep provider runtime trust and approval outside Vaultspec status unless a future ADR introduces an explicit runtime-probe contract.
- Resolve the repository-wide duplicate test-module and optional-package collection issues separately; they do not block the CI-defined gate or this release.

**Verdict: PASS.** The release-blocking HIGH finding is fixed and covered through real API and CLI behavior. The full CI unit target passes 1,761 tests with 1,052 deliberately deselected. The focused provider-native suites, MCP gateway catalogue, generated references, Ruff, Ty, vault checks, and real Claude Code 2.1.210 and Codex CLI 0.144.4 acceptance are green. No unresolved CRITICAL or HIGH finding remains.
