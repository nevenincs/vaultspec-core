---
tags:
  - '#reference'
  - '#reference-publication-contract'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:078583e8199ce9b64939ec82e31357f9cc2b92d35160be7cd504c858a3599dd9'
related: []
---

# `reference-publication-contract` reference: `generated reference surfaces and the release lane`

How this repository generates its CLI reference today, what the MCP reference does
instead, and where the release lane does and does not touch either. Gathered by reading
the generator, its guards, the two reference surfaces, and the three workflows that cut
and publish a release.

## Summary

### One generator, one managed region, two files

`src/vaultspec_core/cli/reference_gen.py` owns the derivable zones of the CLI reference.
Its contract is a marker grammar: `<!-- vaultspec:generated:begin <region-id> -->` and
its matching `end`, with the generator rewriting only the span between them and carrying
every other byte through verbatim (`src/vaultspec_core/cli/reference_gen.py:49`).

Two registries drive it. `MANAGED_REGIONS` holds the region renderers and currently has
exactly one entry, `command-inventory`, rendered by `render_command_inventory`
(`src/vaultspec_core/cli/reference_gen.py:243`). `MANAGED_FILES` holds the files each
region set is applied to (`src/vaultspec_core/cli/reference_gen.py:277`): the bundled
machine-facing reference `src/vaultspec_core/builtins/reference/cli.md`, and the
source-only handbook `docs/CLI.md`, the latter marked `optional=True` so a `--check` run
inside an installed wheel skips it rather than failing. Both files carry the same
`command-inventory` markers - `src/vaultspec_core/builtins/reference/cli.md:44` and
`docs/CLI.md:110` - so the two surfaces cannot diverge in command set or ordering.

The command inventory is introspected from the live Typer app: `_leaf_commands_in_order`
walks `registered_commands` then `registered_groups`, recursing through
`group.typer_instance` and skipping `hidden` entries
(`src/vaultspec_core/cli/reference_gen.py:92`). Rendered output is normalised by
shelling out to the `mdformat --wrap 88` CLI rather than the Python API, so the
generator and the pre-commit formatter hooks cannot disagree on a layout detail
(`src/vaultspec_core/cli/reference_gen.py:363`).

`generate` renders one file and either rewrites it or diffs it under `check=True`;
`generate_all` walks `MANAGED_FILES` and returns one `GenerateResult` per processed file
(`src/vaultspec_core/cli/reference_gen.py:432`, `:470`). The verb is
`vaultspec-core spec reference generate [--check]`
(`src/vaultspec_core/cli/spec_cmd_reference.py:21`).

### Where the check runs

Two enforcement points, both against the live surface only:

- Pre-commit hook `cli-reference-check` runs `spec reference generate --check`, scoped by
  `files:` to `src/vaultspec_core/cli/*.py`, the bundled `reference/cli.md`, and
  `docs/CLI.md` (`.pre-commit-config.yaml:79`).
- `dev/toolchain.py:786` exposes the same command as the `framework reference-check`
  target, surfaced as the `just framework-reference-check` recipe (`justfile:471`).

Neither knows what version the surface belongs to. Both compare HEAD against HEAD.

### The generated block is load-bearing beyond the docs

`src/vaultspec_core/mcp_server/catalog.py` parses the `command-inventory` marker block
out of the shipped `.vaultspec/reference/cli.md` to build the verb inventory the
stateless `discover`/`invoke` gateway is closed over
(`src/vaultspec_core/mcp_server/catalog.py:54`). Verb existence and curated help text
come from the block; per-verb flag schemas are enriched from the installed Typer tree. A
change to the region's rendering is therefore a change to the gateway's input, not only
to a document.

### The MCP reference is hand-written throughout

`docs/MCP.md` carries no `vaultspec:generated` markers - the grep for them returns hits
only in `docs/CLI.md` and `src/vaultspec_core/builtins/reference/cli.md`. Its `## Tools`
section (`docs/MCP.md:196`) documents each tool as a hand-authored `###` subsection:
`find`, `create`, `edit`, `status`, `check`, `plan_progress`, `plan_edit`, `log`, and the
`discover`/`invoke` pair. There is no bundled MCP counterpart to
`builtins/reference/cli.md`, and `dev/guards/` holds no MCP drift guard; the only guard
naming `MCP.md` is `dev/guards/test_cli_language_contract.py`, which checks prose, not
surface.

The live tool surface is enumerable: tools are registered by the `register_*_tools`
functions in `src/vaultspec_core/mcp_server/app.py:141`, and the existing suite reads
them back with `await mcp.list_tools()`
(`src/vaultspec_core/mcp_server/tests/test_tool_surface.py:133`), asserting against a
hand-maintained `_EXPECTED_TOOLS` frozenset at `:32`. Enumeration is async, so a
synchronous generator would drive it through `asyncio.run`.

### Version attribution today

The package version is `0.1.73` in both `pyproject.toml:45` and
`.release-please-manifest.json`, and `__version__` reads it from installed package
metadata (`src/vaultspec_core/__init__.py:34`). That is the same value as the latest
published release, because the release-please pull request that would bump it to `0.2.0`
is open and unmerged. Main's declared version is therefore indistinguishable from the
released one while its command surface is strictly larger.

The MCP server echoes that version into its instructions string and into the `status`
rollup as `tool_schema_version`
(`src/vaultspec_core/mcp_server/tools/orientation.py:268`), and `docs/MCP.md:509` shows
`"tool_schema_version": "0.1.73"` in a sample payload.

The whole correction layer in the generated surfaces is one hand-written sentence:
`docs/CLI.md:2456`, stating that `spec gitignore` and `spec gitattributes` are "not
available in the 0.1.73 release". Nothing generates it, nothing retires it, and no guard
knows it exists.

### The release lane

Three workflows, none of which regenerates or verifies a reference.

- `.github/workflows/release-please.yml` runs on push to main. When a release pull
  request exists it checks out that branch and pushes a regenerated `uv.lock` onto it -
  the established precedent that the release branch is a place where generated artifacts
  are refreshed against the candidate version. On `release_created` it dispatches
  `publish.yml` at the tag and `binaries.yml` at `ref=main`.
- `.github/workflows/publish.yml` is tag-triggered. It builds the wheel, smoke-tests it
  (`dev/smoke/smoke_check.py` under `uv run --isolated`), attests the distribution,
  publishes to PyPI, and verifies the attached assets carry provenance. It has a working
  pattern for exercising a built artifact in isolation, but it inspects only provenance,
  never surface.
- `.github/workflows/ci.yml` runs the test and lint gates.

The release candidate branch is where the version is already the candidate's while the
tree is main's, so anything generated there describes exactly what will be published.

### The precedent for how these claims must be worded

`dev/guards/test_release_provenance.py` holds the wording of version-scoped claims in
`docs/channels.md` under test, and its module docstring records why: an earlier fix wrote
a caveat that expired at a named release, and the guards held it by failing once that
release was cut - on the release-please branch, which is regenerated and force-pushed, so
the repair would have landed under release pressure on the branch least able to hold it.
Claims are worded to stay true rather than to expire
(`dev/guards/test_release_provenance.py:452`, `:481`). The `docs/CLI.md:2456` caveat is
exactly the shape that guard file exists to prevent, on a surface it does not cover.

## Sources

- `src/vaultspec_core/cli/reference_gen.py`
- `src/vaultspec_core/cli/spec_cmd_reference.py`
- `src/vaultspec_core/mcp_server/catalog.py`
- `src/vaultspec_core/mcp_server/app.py`
- `src/vaultspec_core/mcp_server/tests/test_tool_surface.py`
- `dev/guards/test_release_provenance.py`
- `dev/guards/test_cli_handbook_drift.py`
- `.github/workflows/release-please.yml`, `.github/workflows/publish.yml`
- `.pre-commit-config.yaml`, `dev/toolchain.py`, `justfile`
- `docs/CLI.md`, `docs/MCP.md`, `src/vaultspec_core/builtins/reference/cli.md`
