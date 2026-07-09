---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S27'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Wrap every new handler in \_isolated_context and extend the server instructions string to name the nine-tool surface and the tool-schema version, registering all tools through the updated register_tools bootstrap (agent: vaultspec-low-executor)

## Scope

- `src/vaultspec_core/mcp_server/app.py`

## Description

- Export `register_gateway_tools` from the tools package and register the gateway alongside the seven hot tools in `create_server`, so all nine tools are served from one bootstrap; every handler keeps the copied-context isolation wrapper.
- Replace the generic server `instructions` string with a composed one that names each of the nine tools by role and carries the tool-schema version (the package version per ADR Q8) as the third version channel beside `initialize` implementation info and `status` structured output.
- Fix the carried P04 gap where `invoke` passed only flags, leaving verbs that need operands (`vault add <TYPE>`, `vault plan status <TARGET>`, `vault plan step check <PLAN> <STEP>`, `vault feature rename <OLD> <NEW>`) uncallable: collect each verb's ordered positional arguments during Typer introspection into a new `CommandArgument` schema on the catalog entry.
- Add an ordered `positionals` passthrough to `invoke`, placed in the operand slot right after the verb path and ahead of the flags, count-validated against the verb's declared arguments before any spawn, keeping the argv-list/no-shell safety intact.
- Surface each verb's positional arguments in the `discover` payload (a new `ArgumentSchema`) so an agent knows what operands a verb needs and in what order.

## Outcome

- Wired: `src/vaultspec_core/mcp_server/app.py` (nine-tool `create_server`, composed instructions), `src/vaultspec_core/mcp_server/tools/__init__.py` (gateway export).
- Positionals: `src/vaultspec_core/mcp_server/catalog.py` (`CommandArgument`, `_arguments_of`, `_collect_command_schemas`, positional ceiling helpers) and `src/vaultspec_core/mcp_server/tools/gateway.py` (`positionals` parameter, `_validate_positionals`, operand-slot argv construction, `ArgumentSchema` in discover).
- Verified end-to-end: `create_server` lists exactly the nine expected tools; the instructions string names all nine and carries the version; a real `invoke` of `vault add research --feature <tag>` with a positional scaffolds the document and exits clean, and a stray operand on an argless verb is refused before spawn.
- New gateway tests: an end-to-end positional invocation and an argless-verb positional rejection.

## Notes

- The catalog's positional introspection reads Typer/Click `param_type_name == "argument"` and `nargs == -1` for the variadic tail, so a verb with a rest-consuming argument accepts unbounded trailing operands while fixed-arity verbs enforce a ceiling. The count guard is a smuggle-prevention check only; injection is already impossible because every operand is a discrete argv item and no shell is ever invoked.
- Discovered during test authoring that `vault list` declares an optional positional (`[DOC_TYPE]`), so the argless-rejection test targets `vault stats`, which genuinely declares none.
