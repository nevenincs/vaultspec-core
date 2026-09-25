---
tags:
  - '#audit'
  - '#environment-provisioning'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:a63098171ea2dfe6914a6a64cccc20310984a9fd981cc9f78e0ca7f9b3387354'
related:
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-07-13-install-mode-adr]]"
---

# `environment-provisioning` audit: `Credential provisioning and precedence`

## Scope

Installation, runtime configuration, credential resolution and Git protection.
Code discovery used known modules and targeted searches after semantic search failed.

## Findings

### provisioning | medium | Installation cannot provision local runtime settings

`src/vaultspec_core/cli/root_install.py:43` exposes no environment import flags.
`src/vaultspec_core/config/credential.py:146` resolves the process key and a trusted
dependency or dev workspace's root `.env`; a tool installation cannot persist its key.
Native MCP configuration preserves literal environment values, so embedding credentials
there would risk sharing them with generated project configuration.

### precedence | medium | Blank overrides and session caches need explicit semantics

`src/vaultspec_core/config/credential.py:182` treats a blank process value as absent,
allowing a lower file value to enable hosted work. `config/config.py:841` caches one
configuration globally without workspace identity. Persisted settings require an
environment-first, workspace-aware resolver that observes changed inputs.

### protection | high | Ignoring a file does not protect an already tracked secret

`core/gitignore.py:195` owns optional managed ignore entries; `core/git_artifacts.py:179`
automatically untracks some managed paths. Credential provisioning must reject tracked
destinations, establish ignore protection before writing, and restrict file permissions.
The existing staged-artifact guard can reject force-added local credentials.

## Recommendations

Decide the explicit import surface, private file location, merge behavior and override
order in `2026-09-25-environment-provisioning-adr`. Preserve ordinary installation and
mode selection, with no credentials copied into the vault or provider configuration.
Use targeted filesystem, Git, resolver and CLI tests; no hosted API calls are needed.

Primary references: `https://pydantic.dev/docs/validation/dev/concepts/pydantic_settings/`
documents process environment precedence over dotenv and secret files;
`https://git-scm.com/docs/gitignore` explains tracked-file limitations;
`https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets`
recommends environment or stdin instead of secret command-line arguments.

### implementation | low | Provisioning and shared resolution verified

Implemented explicit imports, registry eligibility, private atomic storage, compulsory
ignores, tracked-file refusal and value-free diagnostics. CLI and MCP share the resolver;
the cache follows workspace, environment, store, ignore and Git-index changes. The
existing atomic writer owns durability and cleanup, with a pre-content permission hook.
Editor environment settings precede committed local configuration.

Validation: 161 configuration, installation and editor tests passed; 84 focused storage,
atomic-write, lifecycle and MCP tests passed after the shared-writer integration. These
sets overlap. The MCP test used a real stdio server, observed local credential removal
without restart, compared CLI status, and made no hosted request. The 4 lifecycle tests
also cover value-free JSON errors, disabled managed-ignore maintenance and native MCP
failure preserving existing values. A real Git worktree test verifies separate stores
and indexes. Windows DACL inspection confirms one explicit full-control grant without
inherited grants. A separate-process smoke outside pytest exercised the production
durability path through install, status and full uninstall using a dummy credential.

The broad guard selection found a missing project-context handbook section from the
preceding feature. The section and its flags are documented; all 5 focused handbook
checks pass. The durability guard's duplicate-fsync finding is resolved through the
shared writer. Lint, format, type and reference checks cover the changed surfaces.
