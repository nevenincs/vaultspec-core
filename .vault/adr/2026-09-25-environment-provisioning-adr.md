---
tags:
  - '#adr'
  - '#environment-provisioning'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:7da8e694004693cb0d0f474bd626932df652debac50eec32eb943bbb185fe348'
related:
  - "[[2026-09-25-environment-provisioning-audit]]"
  - "[[2026-09-23-typesafe-search-adr]]"
---

# `environment-provisioning` adr: `Explicit private settings with environment-first resolution` | (**status:** `accepted`)

## Problem Statement

CLI and MCP need the same optional credentials and supported runtime settings without
placing secrets in shared policy, provider configuration or vault records. Evidence is
in `2026-09-25-environment-provisioning-audit`.

## Considerations

Accepted 2026-09-25 under the user's explicit instruction to implement provisioning,
preserve install and upgrade behavior, and give environment overrides normal priority.
This is a distinct persisted local configuration contract; the TypeSafe credential
decision is refined to consume it without changing hosted opt-in or model selection.

## Considered options

- Process environment only: simple but leaves tool installs without local provisioning.
- Provider-native environment values: rejected because generated configuration is shared.
- An explicit, protected project-local store: chosen for shared CLI and MCP behavior.

## Constraints

- Per-command flags precede process environment; process presence, including blank,
  precedes `.vaultspec/.env`, the existing trusted root `.env` credential fallback,
  and defaults. Editor environment settings also precede committed project
  configuration. A blank credential disables hosted calls without falling through.
- Only registry-approved runtime variables can be persisted. Layout, launch, endpoint,
  model and internal markers cannot be supplied by this file. No process-wide loading.
- `install --env NAME` imports from the process; `--env NAME=VALUE` accepts non-secret
  settings only; `--env-file PATH` imports a bounded dotenv file. Explicit entries win
  over the imported file. Only supplied keys replace stored values.
- Fresh provisioning is optional. Upgrade, force, adoption and sync preserve unmentioned
  values. Dry runs write nothing; a failed install does not replace local settings.
- Provisioned secrets remain outside the vault and generated provider configuration.
  Ignore protection is compulsory even if managed-block maintenance is disabled.
  Tracked files and redirected storage paths are refused. Files have restricted local
  permissions; outputs and errors never contain values. The existing commit guard
  rejects staged local credentials. These controls do not promise to prevent deliberate
  bypass of Git hooks or manual disclosure.
- Runtime state is isolated by workspace and refreshed when its inputs change. The
  explicitly provisioned store works in every install mode; the implicit root `.env`
  fallback retains its dependency/dev and interpreter trust boundary.

## Implementation

Registry eligibility, the shared private-store resolver, validated installation
imports, and protected atomic writes implement this contract. The existing filesystem
helper owns replacement and durability; a permission callback runs before content is
written. Direct work is bounded to this provisioning behavior, its tests and current
CLI and environment documentation.

## Rationale

Explicit imports distinguish operator intent from cloned repository content. A dedicated
store lets the MCP and CLI share resolution without embedding secrets in their launch
configuration or requiring a new runtime dependency.

## Consequences

Ordinary keyless installation remains supported. An unsafe or malformed local store is
refused with value-free diagnostics. Full framework uninstall removes its local store;
upgrades and synchronization preserve it. Root `.env` and process values are never
rewritten by the installer.
