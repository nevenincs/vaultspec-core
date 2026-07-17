---
tags:
  - '#research'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-13-install-mode-adr]]'
  - '[[2026-07-14-install-parity-adr]]'
  - '[[2026-07-15-provider-mcp-enrollment-adr]]'
  - '[[2026-07-16-mcp-stdio-lifetime-adr]]'
---

# `mcp-static-launch` research: `side-effect-free MCP launch rendering`

The question: should an MCP client connect ever be able to mutate the governed
project's environment, and is the dependency-mode launch shape
(`uv run python -m <module>`) production-grade or a dev-era artifact? The
question matters because a live incident on 2026-07-17 showed one MCP connect
attempt corrupting this repository's venv: bare `uv run` triggers an implicit
`uv sync`, the sync uninstalled `vaultspec-core` from site-packages and then
died on a pywin32 DLL held open by a running sibling MCP server, leaving every
subsequent connect failing with client error -32000. The evidence picture:
the launch renderer is the single line that omits the `--no-sync` guard every
other dependency-mode surface already carries; the sibling rag definition
seeded in this workspace additionally predates install-parity and still
carries the banned exe-form launch; and rag's shipped tokenized definition
omits the tool-mode extra spec its own packaging requires. The mode
architecture itself (tool/dependency/dev, tokenized definitions, one launch
comparator) is sound and recently decided; the defects are all in the
concrete launch bytes the dependency branch renders and in stale seeded
state, not in the model.

## Findings

### The incident: one bare `uv run` sync corrupted the venv at MCP connect time

An MCP client connect is currently a mutating operation in dependency mode.
The deployed `.mcp.json` launches `uv run python -m vaultspec_core.mcp_server.app`; without `--no-sync`, `uv run` re-syncs the
project environment on every invocation. Reproduced 2026-07-17 on this
workspace: the launch exited code 2 before any JSON-RPC bytes with
`error: failed to remove file .venv\Lib\site-packages\pywin32_system32/pywintypes313.dll: Access is denied. (os error 5)`,
the DLL being held by two long-lived `vaultspec-search-mcp` processes running
from the same venv. A prior interrupted sync of the same shape had already
uninstalled `vaultspec-core` from site-packages entirely (site-packages held
`vaultspec_rag` but no `vaultspec_core`, plus overlapping `pywin32-311` and
`pywin32-312` dist-info residue), so even a sync-free launch then failed with
`ModuleNotFoundError`. The client surfaces all of this as JSON-RPC error
-32000 (connection closed before initialize). The failure is self-inflicted
by the launch shape, not by the server code: the watchdog and tool surface
(`2026-07-16-mcp-stdio-lifetime-adr`, `2026-07-09-mcp-tool-schema-adr`) never
executed.

### The renderer omits the `--no-sync` guard that every sibling surface carries

The single launch comparator `render_launch_for_mode`
(`src/vaultspec_core/core/mcps.py:106-108`) renders dependency mode as
`uv run python -m <module>`. The canonical hook entries for the same mode
render `uv run --no-sync vaultspec-core ...`
(`src/vaultspec_core/core/commands.py:396`), and the firmware CLI-fallback
rule mandates `uv run --no-sync` for agent-driven CLI use
(`.claude/rules/vaultspec-cli.builtin.md`). The MCP launch is therefore the
one dependency-mode surface where invocation implies environment mutation.
The omission is deliberate-by-inertia, not decided: the docstring
(`src/vaultspec_core/core/mcps.py:89-91`) pins the shape as "byte-identical
to the launch every dependency-mode workspace has always synced", carrying
forward the pre-mode-era default that `2026-07-13-install-mode-adr` Q2
inherited without revisiting the sync flag. No test or decision record
asserts that the sync-on-connect behavior is wanted; the install-mode ADR's
own Windows exe-lock consideration argues the opposite direction (launches
must not contend with running processes over environment files).

### The mode architecture is decided and sound; this is a launch-bytes defect

Three accepted decisions already govern this surface and none needs
reopening: `2026-07-13-install-mode-adr` (tool mode default via
`uvx --from <package> python -m <module>`, dependency mode first-class,
module invocation over exe form for the Windows exe-lock class),
`2026-07-14-install-parity-adr` (rag adopts the same tokenized definition and
per-package `workspace.json` map through core's single renderer), and
`2026-07-15-provider-mcp-enrollment-adr` (`.vaultspec/mcps/*.json` is the
only desired-state authority; installation never launches an MCP process).
The observed-shape matcher (`src/vaultspec_core/core/diagnosis/collectors.py:813-873`)
reconstructs candidate shapes through `render_launch_for_mode` itself, so a
change to the rendered bytes propagates to doctor detection automatically -
the single-comparator discipline holds. The consequence cuts both ways:
already-deployed old-shape entries (`uv run python -m ...` without
`--no-sync`) will match neither candidate after the change and report
observed mode `None`, so migration/refresh behavior (sync `--force`,
`install --upgrade`, doctor hint wording) must be settled deliberately.

### This workspace's rag definition is stale pre-parity state with the banned exe-form launch

`.vaultspec/mcps/vaultspec-rag.builtin.json` in this workspace contains the
static `{"command": "uv", "args": ["run", "vaultspec-search-mcp"]}` - venv
exe-form, no mode tokens, no `--no-sync`. This is doubly wrong under current
decisions: exe-form launch is the Windows exe-lock class install-mode Q2
banned (and the two lock-holding processes in the incident were exactly this
venv's `vaultspec-search-mcp.exe`), and a non-tokenized definition bypasses
the mode renderer entirely. The rag repository has already shipped the
correct tokenized form
(`Y:/code/vaultspec-rag-worktrees/main/src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`:
mode tokens plus `_vaultspec_mode_package: vaultspec-rag`,
`_vaultspec_mode_module: vaultspec_rag.server`), so the workspace copy is
stale seeded state, refreshed only by a rag-side re-enrollment. Additionally
`workspace.json` here declares only `vaultspec-core` (dependency mode, floor
0.1.37) with no `vaultspec-rag` entry, so rag's render mode is unpinned in
the very workspace that runs both.

### Rag's shipped definition omits the tool-mode extra its packaging requires

`vaultspec-rag` made `mcp` an optional extra: the base install must not drag
`mcp` (or its Windows `pywin32` transitive), and the MCP server requires
`vaultspec-rag[mcp]`
(`Y:/code/vaultspec-rag-worktrees/main/pyproject.toml:91-95`, entry point
`vaultspec-search-mcp = "vaultspec_rag.server:main"` at line 65). Core's
renderer supports exactly this via `_vaultspec_mode_tool_spec`
(`src/vaultspec_core/core/mcps.py:59,99-101`, docstring example
`"vaultspec-rag[mcp]"`), but rag's shipped builtin does not carry the key, so
a tool-mode render produces `uvx --from vaultspec-rag python -m vaultspec_rag.server` - an environment without the `mcp` dependency, a
guaranteed import failure. Dependency-mode workspaces mask this because the
dev environment installs the extra; tool mode (the decided default for new
workspaces) is silently broken for rag.

### What "static execution" can and cannot mean per mode

The user framing - an MCP connect should be a static tool execution - maps
onto the decided modes as follows. Dependency mode: `uv run --no-sync python -m <module>` is fully static (resolves the existing venv, mutates nothing,
fails honestly with a remediation-shaped error when the venv is stale or
broken instead of self-repairing at connect time). Tool mode: `uvx --from <spec> python -m <module>` is static with respect to the governed project
(never touches its venv) but not hermetic in time - first run and
post-cache-prune runs hit the network, which install-mode already accepted
as a bounded cost. Full hermeticity (a pinned `uv tool install`-provisioned
environment, launch via its absolute interpreter path) was considered and
carries the committed-path portability problem (absolute per-machine paths
cannot be committed to `.mcp.json`) plus the exe-lock class on upgrades;
the two decided shapes plus `--no-sync` are the evidence-favored point. What
the ADR must settle: whether dependency mode gains `--no-sync` as a pure
amendment to install-mode Q2's rendered bytes, how deployed old-shape
entries migrate (doctor signal semantics for shape-mismatch, refresh verb),
and whether rag's missing `_vaultspec_mode_tool_spec` and this workspace's
stale seed are folded into the same feature or tracked as rag-side issues.

### uv semantics: sync-on-connect is documented behavior, `--no-sync` is the surgical guard

Bare `uv run` creating and updating the project environment before executing
is uv's documented design, not a defect: "When used in a project, the project
environment will be created and updated before invoking the command"
(https://docs.astral.sh/uv/reference/cli/#uv-run, fetched 2026-07-17). Of the
guard flags, only `--no-sync` prevents venv mutation: it "avoid[s] syncing
the virtual environment" and implies `--frozen`; `--frozen` alone skips the
lockfile update but still syncs the environment, and `--locked` still syncs.
`uvx` runs in temporary isolated environments, caches after first resolution
("uvx will use the cached version of the tool unless a different version is
requested, the cache is pruned, or the cache is refreshed",
https://docs.astral.sh/uv/concepts/tools/), and never touches a project venv
\- structurally immune to the DLL-lock incident class. Pinning semantics:
`--from 'pkg==X'` resolves from cache thereafter; `pkg@latest` forces a
network refresh every run and belongs nowhere in a connect path. The related
Windows exe-lock defect astral-sh/uv issue 11930 (`uv tool upgrade` failing
on a held binary, reported 2025-03-03) was still open at last verified read;
it concerns `uv tool` upgrades, a cousin of - not the same path as - this
incident, and reinforces the ADR-established preference for module/ephemeral
invocation over held executables.

### 2026 standards: registry and ecosystem distribute Python stdio servers as ephemeral uvx

The current MCP specification revision is 2025-11-25 (supersedes 2025-06-18;
https://modelcontextprotocol.io/specification, fetched 2026-07-17); the stdio
launch contract is unchanged. The official MCP Registry `server.json` schema
distributes Python servers as `registryType: pypi` with `runtimeHint: "uvx"`
and `transport.type: "stdio"`, launching as `uvx <package>@<version>`; no
venv or `uv run` runtime hint exists in the schema
(https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md).
Reference servers agree: `mcp-server-git` and `mcp-server-fetch` both
recommend `"command": "uvx"` configs, with `python -m` after pip install and
Docker as the only alternatives - venv-tethered `uv run` appears nowhere as a
recommended distribution shape
(https://github.com/modelcontextprotocol/servers/blob/main/src/git/README.md,
https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md).
This maps cleanly onto the decided two-mode model: dependency mode is the
dev/self-hosting shape, tool mode is the distribution shape the ecosystem
blesses. The ecosystem's terser `uvx <package>` exe form versus the decided
`uvx --from <package> python -m <module>` module form is a deliberate local
divergence: install-mode Q2 chose module invocation for the exe-lock class,
and both remain valid mitigations per that record.

### Client contract: 5-second connect window, no stdio reconnect, -32000 = crashed child

Claude Code gives stdio servers a 5-second connect timeout (overridable via
`MCP_TIMEOUT`), starts them non-blocking, and never auto-reconnects a dead
stdio server within a session - only HTTP/SSE transports get backoff
(https://code.claude.com/docs/en/mcp). Error -32000 is the child process
exiting before the JSON-RPC handshake, with stdout contamination as the top
documented cause - stdio transport reserves stdout for JSON-RPC, so any
`uv sync` resolver output on stdout corrupts the stream even when the sync
succeeds. Connect-time dependency resolution therefore violates the client
contract twice: a cold resolution can blow the 5-second window, and its
output can poison the handshake. There is no single normative "no sync at
connect" mandate; the convergent convention follows from the latency and
side-effect expectations (non-blocking init, small artifacts, initialization
out of the handshake path).

### Sibling-session boundary

The in-flight `2026-07-17-mcp-stdio-lifetime-plan` (P03.S11 open, branch
`feat/mcp-watchdog-parity`) owns server lifetime after a successful start;
this feature owns the launch bytes before the process exists. No file
overlap: watchdog work lives in `src/vaultspec_core/mcp_server/`, launch
rendering in `src/vaultspec_core/core/mcps.py` and its consumers.

## Sources

- `src/vaultspec_core/core/mcps.py:106-108` - dependency render without `--no-sync`
- `src/vaultspec_core/core/mcps.py:59,89-101` - tool-spec key, byte-identical docstring
- `src/vaultspec_core/core/commands.py:396` - hook prefix `uv run --no-sync vaultspec-core`
- `src/vaultspec_core/core/diagnosis/collectors.py:813-873` - observed-shape matcher
- `.vaultspec/mcps/vaultspec-rag.builtin.json` (workspace copy, stale exe-form)
- `Y:/code/vaultspec-rag-worktrees/main/src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json` - rag shipped tokenized form
- `Y:/code/vaultspec-rag-worktrees/main/pyproject.toml:65,91-95` - `vaultspec-rag[mcp]` optional extra, entry point
- `.vaultspec/workspace.json` - core-only per-package map, dependency mode, floor 0.1.37
- Incident reproduction 2026-07-17, this workspace: `uv run` exit 2, pywin32 DLL lock, missing `vaultspec_core` in site-packages
- https://docs.astral.sh/uv/reference/cli/#uv-run - `uv run` sync semantics, `--no-sync`/`--frozen`/`--locked`
- https://docs.astral.sh/uv/concepts/tools/ - uvx isolated environments and cache semantics
- https://docs.astral.sh/uv/concepts/cache/ - cache refresh and prune controls
- https://github.com/astral-sh/uv/issues/11930 - Windows exe-lock on `uv tool upgrade` (open; comment trail after the original report unverified)
- https://modelcontextprotocol.io/specification - MCP spec revision 2025-11-25
- https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md - `runtimeHint: uvx` for pypi servers
- https://github.com/modelcontextprotocol/servers/blob/main/src/git/README.md - uvx-recommended reference config
- https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md - uvx-recommended reference config
- https://code.claude.com/docs/en/mcp - project-scope `.mcp.json`, 5s connect timeout, `MCP_TIMEOUT`, no stdio reconnect
- https://startdebugging.net/2026/06/fix-mcp-error-32000-connection-closed-in-claude-code/ - -32000 taxonomy (secondary source)
