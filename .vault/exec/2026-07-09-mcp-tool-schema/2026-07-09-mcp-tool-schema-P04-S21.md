---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S21'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the invoke tool: validate the verb path and argument object against the parsed inventory and denylist, build an argv list (never a shell), inject --target from the resolved root_dir, pass --json where the verb supports it, run the installed vaultspec-core binary with a timeout, fold stderr into the error payload, and return parsed JSON or captured stdout, annotated destructive (agent: vaultspec-high-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/gateway.py`

## Description

- Add the `invoke` tool that validates the submitted verb path against the parsed catalog and the static denylist first, raising a protocol error before any process spawns for an unknown or denied verb.
- Build an argv list (never a shell string, never `shell=True`) prefixed by the same interpreter and module entry the server runs under (`sys.executable -m vaultspec_core`), so it works both installed and in the uv development environment; inject `--target` from the resolved root at the global position and append `--json` where the catalog says the verb supports it.
- Render caller arguments into discrete, validated argv items: each key maps to a declared kebab-case flag, value flags emit `--flag value` (a list repeats the flag), boolean flags emit a bare switch, and reserved (`--target`/`--json`/`--help`) or undeclared flags are rejected so no caller text can shadow the injected flags or smuggle an unknown token.
- Run the subprocess with a timeout capturing stdout and stderr, return parsed JSON on a clean `--json` exit and captured text otherwise, and fold a non-zero exit or timeout or JSON-parse failure into a structured error payload while remaining a successful call; annotate the tool destructive and keep the isolation wrapper.

## Outcome

- `invoke` runs the real binary end to end: a read-only verb returns parsed JSON, unknown and denylisted verbs are rejected before spawn, a missing-argument verb folds its stderr and exit code into the structured error payload, and reserved/unknown flags are refused.

## Notes

- The argument object currently models flags only, matching the plan wording and the flag-centric co-occurrence data; verbs requiring positional arguments (for example a plan target) are therefore not yet callable through `invoke`. This is the one functional limitation to weigh for a follow-on, and it is why the non-zero-exit test drives a missing-positional usage error rather than a positional-bearing verb.
