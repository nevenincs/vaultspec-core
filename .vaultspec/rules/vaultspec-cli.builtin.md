---
name: vaultspec-cli
---

# Vaultspec tools

Every `.vault/` mutation, listing, and repair goes through the owning verbs: MCP tools
when connected, else the `vaultspec-core` CLI. Bypassing them produces drift that
`check` flags. A record's body is read as a file.

## Tools

The MCP server exposes `status` (in-flight plans and next open Step), `find` (documents
and features), `create` (scaffold, batchable), `edit` (body prose, batchable),
`plan_progress` (check or uncheck Steps), `plan_edit` (author and restructure Step
rows), `log` (append a Step's ledger rows), `check` (validate and repair), and the
`discover`/`invoke` gateway to every other verb. `invoke` asks for host confirmation on
every call, so the above-Step plan verbs (`tier`, `wave`, `phase`, `epic intent`) and
`vaultspec-core sync` are better run through the CLI even when connected.
`vault feature index`, `spec mcps`, and `uninstall` are CLI-only.

The bundled CLI reference, `.vaultspec/reference/cli.md`, catalogues every command,
flag, and exit code. Run `vaultspec-core <cmd>`, or
`uv run --no-sync vaultspec-core <cmd>` in uv environments; `--dry-run`, `--json`, and
`<cmd> --help` preview and explain. Sync-shaped commands report created, updated,
unchanged, removed, restored, skipped, or failed; only `failed` stops.

## Manual edits

Permitted: body prose of a scaffolded record, including the `proposed`, `accepted`,
`rejected`, or `deprecated` token in an ADR's heading (`superseded` is set by
`vault adr supersede`). Policy sources under `.vaultspec/rules/`, `skills/`, `agents/`,
`hooks/`, and `mcps/` are the user's: propose changes, apply them only on request, then
run `vaultspec-core sync`. Forbidden: frontmatter, filenames, plan structure, Step
checkboxes, new `.vault/` files, and anything inside generated provider directories.
