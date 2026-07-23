---
tags:
  - '#research'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
related: []
---

# `prek-boundary-hardening` research: `pre-commit-config vs prek.toml lifecycle`

When a workspace adopts `prek.toml`, vaultspec-core stops managing the
`.pre-commit-config.yaml` hook set: the scaffold short-circuits, sync leaves the
YAML untouched, and the doctor renders a warn-only advisory telling the operator to
transplant the canonical hooks into `prek.toml` by hand. The question this research
grounds is what the intended lifecycle of `.pre-commit-config.yaml` should be once
`prek.toml` owns the hook boundary, and where the current boundary sheds bugs. The
evidence picture: the boundary is governed by a single opaque existence check on
`prek.toml`, applied in three unconnected places, with no parser, no migration, and
no cleanup, so the operator is left with a stale YAML file and a manual instruction
that the tooling can neither verify nor complete.

## Findings

### The boundary is a single opaque existence check, replicated in three places

Every branch of the boundary keys off `(target / "prek.toml").exists()` and never
reads the file's contents. The scaffold short-circuit is at `src/vaultspec_core/core/commands.py:803`;
the diagnosis override that promotes any non-`COMPLETE` YAML state to `UNREFRESHABLE`
is at `src/vaultspec_core/core/diagnosis/collectors.py:795`; the orphaned-lock-sentinel
prune that fires after a checkout migrates to `prek.toml` is documented at
`src/vaultspec_core/core/gitignore.py:138` and driven from `src/vaultspec_core/core/commands.py:1544`.
No code path anywhere parses `prek.toml` as TOML or inspects it for the vaultspec
hook IDs. The consequence is that the boundary cannot distinguish a workspace that
has correctly transplanted the hooks from one that has an empty `prek.toml` and no
hooks anywhere; both are treated identically.

### `UNREFRESHABLE` is emitted on existence alone, so it fires as a false positive

`collect_precommit_state` promotes the YAML signal to `UNREFRESHABLE` whenever the
YAML state is not `COMPLETE` and `prek.toml` exists (`collectors.py:794-797`). Because
`_collect_precommit_yaml_state` returns `COMPLETE` only when the canonical hooks are
present in `.pre-commit-config.yaml` with canonical entries (`collectors.py:843-858`),
a workspace that has already done the right thing - moved the hooks into `prek.toml`
and left a stale or hook-less `.pre-commit-config.yaml` behind - reports
`UNREFRESHABLE` indefinitely. The signal says "your hooks cannot be refreshed" even
when the hooks are perfectly healthy inside `prek.toml`. The advisory text at
`src/vaultspec_core/cli/spec_cmd.py:2328-2332` then instructs the operator to perform
a transplant that may already be done. This is the structural reason the subsystem
keeps producing warning-noise bugs like #231.

### The remediation is manual and unassisted; there is no migration verb

The scaffold's own docstring states the contract plainly: "The operator is expected
to transplant hooks into `prek.toml` manually" (`commands.py:794-795`), echoed by the
one-shot info and warning logs at `commands.py:804-816`. The `flow-bugs` ADR that
introduced this branch (D3) recorded the same scope boundary explicitly: "No hooks
are transplanted into `prek.toml`; that is out of scope for this release"
(`.vault/adr/2026-04-21-flow-bugs-adr.md:59`). There is no verb that reads the
canonical hook definitions and emits `prek.toml` syntax. The canonical hook set is
already available in structured form via `canonical_precommit_hooks_for_mode`
(`commands.py:704-714`) and `canonical_hook_entries_for_mode` (`commands.py:717-722`),
keyed by the mode resolved from the workspace declaration, so the raw material for an
assisted migration exists but is only ever rendered to YAML.

### The `spec hooks` verb namespace is already taken by declarative event hooks

The issue suggests offering an assisted "`spec hooks` migration path", but the
`spec hooks` command group already exists for an unrelated concern: declarative,
event-triggered workspace hooks authored under `.vaultspec/` (for lifecycle events
such as `vault.document.created`), with `list`/`add`/`show`/`edit`/`rename`
subcommands at `src/vaultspec_core/cli/spec_cmd.py:1256-1448`. These are shell hooks
run by the vaultspec hook engine, not git pre-commit hooks. Any migration verb for
the pre-commit/prek boundary must avoid colliding with this namespace; the naming and
placement of a migration command is therefore an open design question, not a given.

### Orphan detection today covers only the lock sentinel, not the YAML config itself

The one piece of automatic cleanup that already crosses this boundary is narrow: when
a checkout migrates to `prek.toml`, the `.pre-commit-config.yaml.lock` advisory-lock
sentinel is pruned so it does not linger in `git status` (`gitignore.py:134-167`,
called from `commands.py:1544-1548`). The prune is deliberately conservative - it only
removes empty sentinels it owns (`gitignore.py:158`). Nothing analogous exists for the
superseded `.pre-commit-config.yaml` itself: the `flow-bugs` ADR notes the file "is
simply not generated, so it will not appear in the working tree unless pre-existing"
(`.vault/adr/2026-04-21-flow-bugs-adr.md:105`), which is true for fresh installs but
says nothing about a workspace that adopts `prek.toml` after a YAML config already
exists. That pre-existing-file case is exactly the orphan the issue flags, and it has
no detection or cleanup path.

### Uninstall still touches the YAML config even under prek

The uninstall path is unaffected by the prek short-circuit: `_ALL_MANAGED_HOOK_IDS`
still strips vaultspec hooks from a legacy `.pre-commit-config.yaml` if one exists
alongside `prek.toml` (`.vault/adr/2026-04-21-flow-bugs-adr.md:61`). This asymmetry is
worth naming for the lifecycle decision: install/sync refuse to write the YAML under
prek, but uninstall will still edit it. A coherent lifecycle model should reconcile
whether prek workspaces have a managed YAML surface at all.

### The recent bug cluster shares one root: an under-specified boundary

This cycle produced #236 (bare spec-check gate deadlock), #241 (sync YAML
comment/quote loss), #243 (fixture flake around rule staleness), and #231/#232
(spurious `UNREFRESHABLE`-adjacent warning). #232 (the merge at HEAD, commit
`88e18e0f`, "fix: recognize unrefreshable prek sync state") added the resolver no-op
branch at `src/vaultspec_core/core/resolver.py:944-948` so `_resolve_precommit` stops
falling through to the unknown-signal warning for `UNREFRESHABLE`. That is a symptom
fix: the resolver now handles the signal, but the signal itself is still emitted on
existence alone. The common thread across the cluster is that the prek/sync/self-managed-hook
boundary is expressed as scattered existence checks and round-trip YAML edits with no
single owner of the invariant "who manages the hooks here, and in what file". The
`_precommit_yaml` round-trip handler (`commands.py:743-762`) that #241 concerns, the
scaffold short-circuit, the diagnosis override, and the sentinel prune are four
independent expressions of the same boundary.

### External assumption: prek reads `prek.toml` exclusively

The code embeds a factual assumption about the `prek` tool - "prek reads `prek.toml`
exclusively; vaultspec will not refresh the YAML hooks" (`commands.py:812-813`) - and
that presence of `prek.toml` makes `.pre-commit-config.yaml` a conflicting duplicate.
This is the premise the whole boundary rests on. It was not re-verified against the
current `prek` release during this research and should be confirmed before committing
to a migrate-and-remove lifecycle, since prek's actual config-discovery precedence
(whether it errors, warns, or silently ignores one file when both exist) determines
whether leaving the YAML in place is merely untidy or actively breaking. Flagged as an
unverified general-knowledge/embedded-assumption claim.

### Not investigated

The exact TOML schema `prek` expects for local system hooks was not verified against
the tool's documentation; the assisted-migration renderer will need that confirmed.
The behavior of `prek` when both config files are present (hard error vs precedence)
was not empirically tested. Whether any real vaultspec-managed workspace currently
uses `prek.toml` (adoption rate) was not surveyed.

## Sources

- `src/vaultspec_core/core/commands.py:704` - canonical hook renderers by mode
- `src/vaultspec_core/core/commands.py:743` - `_precommit_yaml` round-trip handler
- `src/vaultspec_core/core/commands.py:772` - `_scaffold_precommit` and the prek short-circuit
- `src/vaultspec_core/core/commands.py:1544` - orphaned-sentinel prune call site
- `src/vaultspec_core/core/diagnosis/collectors.py:776` - `collect_precommit_state` and the `UNREFRESHABLE` override
- `src/vaultspec_core/core/diagnosis/collectors.py:800` - `_collect_precommit_yaml_state`
- `src/vaultspec_core/core/diagnosis/signals.py:97` - `PrecommitSignal` enum members
- `src/vaultspec_core/core/resolver.py:881` - `_resolve_precommit` and the `UNREFRESHABLE` no-op branch
- `src/vaultspec_core/core/gitignore.py:134` - `prune_orphaned_lock_sentinels`
- `src/vaultspec_core/cli/spec_cmd.py:1256` - `spec hooks` declarative event-hook command group
- `src/vaultspec_core/cli/spec_cmd.py:2312` - doctor precommit row and `UNREFRESHABLE` advisory text
- `src/vaultspec_core/tests/cli/test_convergence_advisories.py:47` - existing `UNREFRESHABLE` advisory tests
- `src/vaultspec_core/tests/cli/test_flow_bugs.py:324` - prek short-circuit tests (D3)
- `.vault/adr/2026-04-21-flow-bugs-adr.md:57` - D3, the decision that introduced the prek short-circuit
- commit `88e18e0f` - #232 resolver no-op branch recognizing the unrefreshable state
- GitHub issues #231, #236, #241, #243 - the recent prek/sync boundary bug cluster
