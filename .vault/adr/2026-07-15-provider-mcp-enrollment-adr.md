---
tags:
  - "#adr"
  - "#provider-mcp-enrollment"
date: '2026-07-15'
related:
  - "[[2026-07-15-provider-mcp-enrollment-research]]"
  - "[[2026-07-15-provider-mcp-enrollment-reference]]"
  - "[[2026-04-11-mcp-registry-adr]]"
supersedes:
  - '2026-04-11-mcp-registry-adr'
modified: '2026-07-15'
---

# `provider-mcp-enrollment` adr: typed provider-native MCP enrollment with explicit scopes | (**status:** `accepted`)

## Problem Statement

The accepted MCP registry decision incorrectly makes one JSON deployment target stand
for every provider. Core consequently reports Codex healthy without configuring the
surface Codex reads. A replacement decision must retain the canonical registry and
package-mode renderer while making deployment, ownership, scope, status, migration,
and uninstall native to each enrolled host.

## Considerations

- Host scope and schema facts are grounded in
  `2026-07-15-provider-mcp-enrollment-research`.
- Existing lifecycle insertion points and the companion-facing API are grounded in
  `2026-07-15-provider-mcp-enrollment-reference`.
- The source registry and mode-aware launch authority from
  `2026-04-11-mcp-registry-adr` remain stable and reusable.
- User and local configuration writes cross the workspace boundary and require an
  explicit scope authorization.
- Desired state and observed ownership must remain distinct so a sidecar cannot silently
  become a second registry.

## Considered options

- Keep shared `.mcp.json` and add a Codex copy step: rejected because it preserves the
  false provider abstraction, duplicates lifecycle behavior, and cannot model scopes.
- Invoke each host's `mcp add/remove` commands: rejected as the primary writer because
  Codex exposes no project-scope flag, host command defaults differ, and round-trip
  preservation and dry-run would depend on external mutations.
- Parse and reserialize whole native files: rejected because it destroys comments and
  user formatting in shared TOML and expands the corruption blast radius.
- Use typed targets with provider adapters, managed TOML blocks, and ownership sidecars:
  selected because it gives one lifecycle contract while preserving native schemas and
  user content.

## Constraints

- `.vaultspec/mcps/*.json` remains the only desired-state authority.
- Dependency/dev and tool launch shapes continue through the existing mode renderer.
- Canonical mode metadata separates declaring-package identity from an optional
  tool-mode distribution spec; both are stripped before host rendering.
- Provider-native files contain only host-supported configuration and comments.
- Project is the default scope. User and Claude-local scopes require an explicit option;
  Codex-local is invalid.
- Fresh install must reconcile the selected providers even before their manifest write.
- Dry-run writes no project, host, ownership, or manifest bytes.
- Unforced sync never adopts a same-name entry without affirmative legacy ownership.
- A provider-only operation never mutates another provider or scope.
- Installation never launches an MCP process; hosts retain trust and approval control.

## Implementation

Introduce typed scope, target-format, target, normalized-definition, and ownership
records above the deployment writers. Target resolution maps Claude project, local, and
user scopes plus Codex project and user scopes to their native stores and rejects invalid
combinations. Provider adapters render normalized stdio definitions to Claude JSON or
Codex TOML and report unsupported fields.

Project ownership is recorded under Vaultspec workspace state. Explicit user-scope
ownership is recorded under Vaultspec user state. These records contain only target
identity, managed names, and observed fingerprints. Codex project and user tables are
also bounded by a comment-only managed block so unrelated TOML remains byte-stable.

The JSON migration transfers legacy `_vaultspecManaged` evidence into ownership state
and removes the non-host key. Entries without affirmative ownership remain external;
force is the only adoption path. Prune and uninstall act exclusively on recorded
ownership. Status aggregates selected native targets and is green only when every
selected enrolled provider is synchronized.

Keep `mcp_sync` as the public package-aware reconcile seam, extended with provider and
scope. Preserve `mode` and `force_managed` so companion packages can use one canonical
definition and one public call. Add matching provider/scope controls to status and
uninstall and pass selected providers directly during fresh install. Root install,
upgrade, sync, and uninstall default to project scope and never touch user state unless
the operator explicitly requests it.

Extend the single launch renderer with an optional tool distribution spec. The existing
package metadata continues to select committed workspace mode; only tool mode substitutes
the optional spec into `uvx --from`. Definition collection validates and strips the new
metadata key before either provider adapter sees the definition.

## Rationale

Typed target adapters are the only option that satisfies both host contracts without
forking the canonical registry or allowing provider-specific logic into companion
packages. External ownership state is required by the host-valid-schema constraint,
while the managed TOML block is required by the user-content round-trip constraint.
The explicit scope matrix follows the consent boundary established by
`2026-07-15-provider-mcp-enrollment-research`; the public seam follows the existing
architecture mapped by `2026-07-15-provider-mcp-enrollment-reference`.

## Consequences

- Codex and Claude receive equivalent lifecycle semantics through different native
  files, and status can no longer be green against an irrelevant file.
- Claude's working project `.mcp.json` behavior remains intact while its Vaultspec-only
  top-level key is retired.
- Companion packages gain a stable provider/scope reconcile API and no longer need to
  infer deployment format.
- Ownership migration becomes conservative; some legacy same-name entries will require
  one explicit force adoption rather than being claimed automatically.
- User-scope support adds cross-workspace conflict and locking concerns that project-only
  code did not have; acceptance must isolate configuration homes and exercise real host
  CLIs.
- `2026-04-11-mcp-registry-adr` is superseded because its provider-agnostic deployment
  premise is replaced, while its canonical source-registry decision is carried forward.
