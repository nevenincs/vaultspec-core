---
tags:
  - '#audit'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# `mcp-tool-schema` audit: `nine-tool MCP server rebuild review`

## Scope

Mandatory code review (plan step S30) of the full `mcp-tool-schema` MCP server rebuild across phases P01-P05 (diff `0a1a102..HEAD`), plus the shared-core extractions it required. Reviewed against the accepted ADR and the reconciliation reference. Covered: `invoke` subprocess safety, owning-verb routing (no reimplementation), the batch/blob-hash concurrency contract and unified envelope, `isError` and annotation fidelity, extraction fidelity, concurrency isolation, test integrity, and standards. Tooling verified live: `ruff check` and `ty check` clean; the canonical gate `pytest src/vaultspec_core -m unit` is green at 1591; the MCP and edit-engine suites pass. Verdict: PASS - no Critical or High findings. One medium latent-correctness item and three low hardening items were found and have all been fixed in follow-up commits.

## Findings

### invoke-boundary-safe | none | The gateway subprocess boundary has no shell or argument-injection path

The verb path is validated against the marker-parsed catalog and the static denylist before any spawn; execution is always an argv list to `subprocess.run` with no `shell=True`; `--target` is server-injected from the resolved root; a timeout is always present; reserved flags (`--target`/`--json`/`--help`) and unknown flags are rejected; positionals are count-validated against the verb's declared arity and land after an already-resolved subcommand so they cannot mutate the verb path. No argument-injection, extra-verb, or denylist-bypass path could be constructed. Values only ever enter as discrete validated argv items.

### batch-envelope-correct | none | The batch and blob-hash reconciliation contract is faithful

Per-item results with no all-or-nothing; the `ok`/`mixed`/`failed` reducer matches the CLI envelope; `expected_blob_hash` compares the git-blob-OID of pre-write on-disk bytes and genuinely raises on conflict; the post-write hash is returned for chaining; intra-batch ops apply sequentially against fresh on-disk bytes with dependency validation seeing earlier same-batch items; `section_not_found` is honest; partial failures let later items proceed.

### isolation-hollow-for-async | medium | The per-request context isolation wrapper did not actually isolate async handler bodies (FIXED)

`isolation.py` ran `ctx_copy.run(fn, *args, **kwargs)` where `fn` is an `async def`, which only builds the coroutine object inside the copied context; the coroutine body then executed under `await coro` in the ambient task context, so contextvar mutations inside a handler were not isolated - contrary to the docstring and the ADR's inviolable concurrent-request-isolation constraint. Harmless at the time (`init_paths` runs once at startup and every handler only reads `_get_ctx()`), but a latent leak the moment any handler mutated a path contextvar per request. Resolution: the wrapper now constructs the coroutine and creates the task inside the copied context (`task = ctx_copy.run(asyncio.ensure_future, coro); return await task`) so the task adopts `ctx_copy` and every await point runs isolated; docstring corrected. Verified non-tautologically: the new non-leakage test fails against the old hollow implementation and passes against the fix, and a second test asserts two concurrent handlers never observe each other's mutation.

### invoke-positional-dash | low | A positional beginning with a dash could be parsed as an option (FIXED)

Reserved-flag rejection was enforced only for options, not for `positionals`; a `-`-leading positional would be parsed by Click as an option rather than an operand. Not exploitable (cannot forge a verb path or exceed declared flag capability), but a defense-in-depth gap. Resolution: `_validate_positionals` now rejects any operand beginning with `-` before spawn; a test confirms `--json`/`--target`/`-x` positionals are refused with nothing scaffolded.

### normalize-silent-dotdot | low | Feature/tag normalization silently stripped embedded double-dots (FIXED)

`normalize_feature_tag` deleted embedded `..` (`a..b` -> `ab`) rather than rejecting, which could mask a typo into a valid-but-different token (path traversal was already neutralized separately). Resolution: removed the silent `..` deletion so any residual `.` fails the kebab pattern; `a..b` and `a.b` are now rejected while traversal cases still fail; dedicated normalizer test added.

### find-limit-global | low | `find` document-search applies limit to the concatenation of types (DOCUMENTED)

An early high-count type can crowd out later types under the global cap. Behavior is honest; resolution was the smallest honest change - the `find` and `_find_documents` docstrings now state explicitly that `limit` is a single global cap applied in type-list order, with a regression test pinning the semantics.

### standards-and-tests | none | Standards and test integrity are met

`ty` and `ruff` clean; Google+Sphinx docstrings; no new dependencies; no shadow of the `mcp` SDK package; `isolated_context` on all nine handlers; owning-verb routing confirmed (creation via `create_vault_doc` + `generate_feature_index`, edits via `execute_edit`, plan mutation via `step_ops` + `guard_plan_write`, orientation/check via `compute_rollup`/`compute_trace`/`run_all_checks`, with no logic authored in `mcp_server/`). Tests use WorkspaceFactory over a real filesystem, drive the real in-memory FastMCP session, and `invoke` spawns the real `-m vaultspec_core` binary; no mocks, stubs, skips, or tautologies observed.

## Recommendations

Status: PASS. The nine-tool surface is sound, faithful to the ADR and reconciliation reference, and safe to merge. The medium latent isolation defect and all three low hardening items have been fixed with regression tests; the full canonical gate remains green at 1591 and the MCP suite passes. No further blocking work: the surface can ship through the existing `.vaultspec/mcps/vaultspec-core.builtin.json` registry unchanged. A future enhancement worth tracking is enriching the generated CLI reference help text, since it is the verbatim `discover` payload and its quality bounds long-tail agent success.
