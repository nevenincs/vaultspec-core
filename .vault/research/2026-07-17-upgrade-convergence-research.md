---
tags:
  - '#research'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-17-mcp-static-launch-adr]]'
  - '[[2026-07-17-mcp-static-launch-research]]'
  - '[[2026-07-13-install-mode-adr]]'
  - '[[2026-07-14-install-parity-adr]]'
---

# `upgrade-convergence` research: `do legacy launch shapes converge on upgrade`

The question: does a legacy workspace (bare uv-run MCP launch, pre-parity
exe-form seed, pre-mode declaration, stale hook entry) actually converge to
the mandated launch-hygiene standard on its next `install --upgrade` or
`sync`, and if not, which machinery must change. It matters because the
static-launch amendment (`2026-07-17-mcp-static-launch-adr`) changed the
canonical launch bytes for every dependency-mode workspace in existence, and
the remediation its documentation promises only works with an explicit
`--force`. The evidence picture: hooks converge unconditionally and
migrations converge unconditionally, but MCP managed entries - the surface
the amendment changed - never converge without `--force`; plain `sync` warns
and skips forever, `install --upgrade` skips the same way unless the mode
flipped, and the mode-flip force seam covers only core's own entry, never a
companion's. The ownership sidecar already records a content fingerprint of
every managed entry that could distinguish a safely-updatable untouched
entry from a hand-edited one, but the merge algorithm discards it. The
versioned migrations registry runs on upgrade and lazily on every vault
command regardless of flags or floors, making it the proven vehicle for
one-time convergence; no migration exists for launch shapes.

## Findings

### MCP managed entries never converge without an explicit force

The merge algorithm (`src/vaultspec_core/core/mcps.py:946-998`,
`_apply_server_merge`) compares each deployed managed entry against the
newly rendered definition: equal counts as unchanged, different counts as
"differs from its definition (use --force to overwrite)" and is skipped
with a warning. Any renderer byte change - the `--no-sync` amendment being
the live example - therefore turns every managed entry in every deployed
workspace into a permanent skip-and-warn on plain `sync`. The upgrade path
inherits the same gate: `sync_provider(sync_target, force=force, ...)`
passes the operator's `--force` through
(`src/vaultspec_core/core/commands.py:1363`), and the deliberate follow-up
seam fires only `if mcp_mode_flipped and not force`, scoped to
`force_managed=frozenset({"vaultspec-core"})`
(`src/vaultspec_core/core/commands.py:1372-1385`) - its own comment
preserves "today's force-gated semantics for a same-mode divergent entry."
Consequence: the drift-hint wording shipped with the static-launch
amendment ("refresh with `spec mcps sync --force` or `install --upgrade`")
overstates the second remediation - a bare `install --upgrade` does not
refresh a same-mode legacy entry, and a companion package's entry is not
refreshed even on a mode flip.

### The ownership fingerprint already distinguishes untouched from hand-edited entries, but is discarded

Every sync records a sha256 content fingerprint of exactly what vaultspec
wrote for each managed entry (`src/vaultspec_core/core/mcps.py:887-915`,
`_fingerprint` stored via `_set_owned_names`), yet the read side
(`_owned_names`, `src/vaultspec_core/core/mcps.py:893-898`) returns only
the name set and drops the fingerprints. The information needed for safe
unconditional convergence is therefore already persisted: a deployed entry
whose bytes still match its recorded fingerprint is provably untouched
since vaultspec wrote it, and rewriting it to the new canonical shape
cannot destroy user content; an entry whose bytes mismatch the fingerprint
was hand-edited and deserves today's skip-and-warn. The current force gate
treats both cases identically, which is why convergence requires the
blunt `--force` (which ALSO overwrites hand-edited and adopts external
entries - a bigger hammer than convergence needs).

### Hooks already converge unconditionally; the prek.toml path is the one hole

`_scaffold_precommit` (`src/vaultspec_core/core/commands.py:741-`) runs on
every install and upgrade, and "existing hooks with matching IDs are
updated to the canonical entry" for the resolved mode - a legacy hook
entry converges with no flag. The exception: when `prek.toml` exists the
scaffold is skipped entirely with a log line telling the operator to
transplant hooks manually, so a prek.toml workspace's stale hook entries
persist indefinitely with no doctor signal beyond the log.

### The migrations registry is the proven no-flag convergence vehicle

`src/vaultspec_core/migrations/__init__.py:1-31`: versioned migrations
declare a target release version, expose an idempotent
`migrate(workspace)`, and the driver runs every entry whose
`target_version` exceeds the manifest's recorded `vaultspec_version` -
triggered by `install --upgrade`, lazily by any `vaultspec-core vault ...`
command via the scanner, and explicitly by `migrations run`. Six shipped
migrations (`m_0_1_17` through `m_0_1_35`) establish the pattern, including
provider-file rewrites (`m_0_1_24_codex_agents_dedup`). This satisfies
"regardless of provisioned version": the version comparison is a floor on
the migration, not on the workspace, so any workspace below the target
converges the first time any triggering verb runs. No migration exists for
MCP launch shapes; one that routes through `mcp_sync` with a scoped
force-managed set would reuse the owning verb rather than hand-rewriting
host files.

### Version floors never block convergence; the render bridge holds legacy workspaces in dependency shape by design

The floor check refuses only when the RUNNING package version is below the
workspace's declared `minimum_version`
(`src/vaultspec_core/core/resolver.py:901,971`) - an old floor never
prevents a newer core from upgrading the workspace, so no floor-side change
is needed for convergence. Separately, `resolve_render_mode`'s legacy-absent
bridge (`src/vaultspec_core/core/workspace_mode.py:860-900`) deliberately
renders an undeclared package as DEPENDENCY so a pre-mode workspace is not
silently flipped to tool shape by a routine sync; `install --upgrade`'s Q6
inference records the real mode. Convergence must preserve this bridge:
the target of convergence is the guarded shape of the workspace's OWN mode,
never a mode change.

### Stale companion seeds are outside core's write authority

The pre-parity exe-form companion seed (static `uv run vaultspec-search-mcp`) lives in the workspace's `.vaultspec/mcps/` and is
owned by the companion's own enrollment
(`2026-07-17-mcp-static-launch-research`, rag findings; rag issue 231).
Core's upgrade cannot rewrite a companion's builtin definition without
crossing the enrollment boundary. What core CAN do within its authority:
the doctor can flag a definition whose name matches a known companion but
whose content is a static non-tokenized launch as a stale seed with a
"re-run the companion's install --upgrade" hint, and the migration that
converges managed HOST entries still applies to whatever the stale seed
last rendered.

### What the ADR must settle

The evidence favors three coordinated changes, each bounded to existing
machinery: (1) fingerprint-verified convergence in the merge algorithm -
a managed entry whose bytes match its recorded fingerprint updates to the
new canonical shape on plain `sync` and upgrade without `--force`,
hand-edited entries keep skip-and-warn (a new narrow gate, not a wider
`--force`); (2) a registered migration targeting the next release that
re-renders managed MCP entries through `mcp_sync` for every package in the
workspace declaration, converging all legacy workspaces on their first
triggering verb regardless of flags; (3) upgrade's mode-flip force seam
widened from core-only to every declared package. Open questions the ADR
must decide: whether fingerprint-verified convergence subsumes the
migration (the migration reaches workspaces that never run sync but do run
vault verbs - complementary, not redundant), whether the doctor gains the
stale-companion-seed signal, and whether prek.toml workspaces get a doctor
warning for unrefreshable hook entries or stay log-only.

## Sources

- `src/vaultspec_core/core/mcps.py:887-915` - fingerprint recorded per managed entry
- `src/vaultspec_core/core/mcps.py:893-898` - `_owned_names` discards fingerprints
- `src/vaultspec_core/core/mcps.py:946-998` - `_apply_server_merge` force gate
- `src/vaultspec_core/core/commands.py:741-` - `_scaffold_precommit` unconditional hook convergence; prek.toml skip
- `src/vaultspec_core/core/commands.py:1363` - upgrade passes operator `--force` through
- `src/vaultspec_core/core/commands.py:1372-1385` - mode-flip seam, core-only, same-mode divergence preserved
- `src/vaultspec_core/core/workspace_mode.py:860-900` - legacy-absent dependency render bridge
- `src/vaultspec_core/core/resolver.py:901,971` - floor refuses only when running version below minimum
- `src/vaultspec_core/migrations/__init__.py:1-31` - versioned idempotent migrations, upgrade + lazy scanner + CLI triggers
- `src/vaultspec_core/migrations/m_0_1_24_codex_agents_dedup.py` - precedent for provider-file migration
