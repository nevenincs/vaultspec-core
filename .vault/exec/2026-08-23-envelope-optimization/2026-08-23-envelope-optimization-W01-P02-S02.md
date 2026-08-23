---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5a2ea704c0d399ef47a8f45bdafbd16d829368778a549a4c61feb45ca36b65b1'
step_id: 'S02'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---
# Return an explicit result object carrying a summary text block so the transport stops emitting a second copy

## Scope

- `src/vaultspec_core/mcp_server/tools`

## Description

- Add a compact-result wrapper module providing a decorator that returns the wire result
  object directly, so the transport stops synthesising a second rendering of every payload.
- Apply the decorator at all nine tool registration sites across the document, orientation,
  plan and gateway modules.
- Add one-line summarisers for the orientation rollup, the health check, batch results, verb
  discovery and verb invocation; use a shape-only default elsewhere.
- Cap the summary line at 200 characters so the text channel cannot grow into a second data
  channel and reintroduce the defect.

## Outcome

Measured against the 10,476-document benchmark corpus. Totals are text bytes plus structured
bytes on the same call.

| call | before | after | reduction |
| --- | --- | --- | --- |
| orientation rollup | 274,751 | 115,011 | 58.1% |
| health check | 883,863 | 402,967 | 54.4% |
| document search, default | 10,778 | 4,802 | 55.4% |
| document search, one type, twenty rows | 25,638 | 12,232 | 52.3% |

Text blocks on a twenty-row search fell from twenty to one, and the duplicate share is zero on
every call measured.

Two things the measurement showed that the audit had not. The duplicated half was the larger
half: the text rendering is pretty-printed while the structured payload is not, which is why
the reductions land above half rather than at it. And the health check was 883,863 bytes,
roughly 255,000 tokens, so it exceeded a 200,000-token context window on its own against a
corpus that is essentially healthy.

The transport's own escape hatch made this safe: a caller-supplied result object is returned
untouched after its structured content is validated against the output model. Preserving the
wrapped function's annotations means schemas still derive from the declared return types, and
the tool surface measured byte-identical at 43,919 characters before and after, confirming the
wire contract is unchanged apart from the text channel.

Verification: the MCP server suite passes at 100 tests, the full repository suite passes at
1,632, lint and format are clean, and the type checker is clean across the whole MCP server
package.

## Notes

Every call measured remains far outside the budget this campaign's decision record assigns it.
The rollup is 5.5 times its tier and the health check 29 times its tier after this change. The
multiplier is gone; the payloads themselves are untouched and belong to later Waves. Reading a
58% reduction as success would misstate the position.

The full-repository run reported one failing test, `test_real_hosts_recognize_isolated_user_enrollment`
in the CLI host suite. It was verified against a clean tree with this Step's work set aside and
fails identically there, so it is pre-existing and unrelated. Worth recording separately: that
run exited zero despite the failure, so the exit code could not be trusted to detect it.

The type checker rejected four unknown-argument sites and one unnecessary ignore comment in the
new code; all were corrected rather than suppressed.
