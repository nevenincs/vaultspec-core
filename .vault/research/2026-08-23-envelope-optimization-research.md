---
tags:
  - '#research'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d8b392f80e80b60ed15bfcbfbdf492aa7178b57a8c59ea60941f2cb56c45d790'
related: []
---
# `envelope-optimization` research: `MCP and CLI return-envelope saturation audit`

vaultspec-core sits in an agentic LLM coding pipeline, so every MCP tool result and CLI
`--json` payload lands directly in a model context window. A five-part audit measured the
return surface against this worktree's vault (1,222 documents, 129 features) and against a
10,476-document corpus cloned from a production vault. The question was whether any return
path scales with vault size rather than with a bounded envelope. It does: the largest
measured payload is 11.2 MB from a single non-mutating command at 1,222 documents, and the
orientation call every session begins with costs roughly 75,000 tokens at 10,476 documents.
The evidence below frames what must be bounded and what the trade-offs are; the ADR settles
the budget and the policy.

## Findings

### Payloads are unbounded by contract, not by accident

`src/vaultspec_core/vaultcore/checks/_base.py:206` caps the human render at 50 diagnostics,
and its docstring states the cap points at `--json` for the full set.
`src/vaultspec_core/cli/rendering_shapes.py:47` and `:283` restate the premise: JSON data
carries the full per-row payload with no truncation. All five truncation constants in the CLI
(`src/vaultspec_core/cli/_repair_render.py:21`, `src/vaultspec_core/cli/status_cmd.py:138`,
`src/vaultspec_core/vaultcore/checks/_base.py:206`) apply to the human render path only. The
unboundedness is a specified property of the contract, written when the machine consumer was
assumed to be a script rather than a context window.

Of 137 leaf CLI commands, 130 carry `--json`; roughly 30 return payloads that are O(vault) or
O(matches) with no cap, and exactly one (`status`) accepts a `--limit`.

### Measured payload sizes

Against 1,222 documents unless stated. Ratio is JSON bytes over the human form of the same
invocation.

| command | JSON bytes | human bytes | ratio | scaling |
| --- | --- | --- | --- | --- |
| `vault graph --metrics` | 11,175,730 | 4,794 | 2331x | quadratic |
| `vault graph` | 11,175,729 | 77,056 | 145x | quadratic |
| `vault list` | 510,855 | 96,078 | 5.3x | linear in documents |
| `status` | 60,001 | 5,166 | 11.6x | linear in features |
| `vault feature list` | 39,400 | 9,742 | 4.0x | linear in features |
| `vault check all` (clean vault) | 6,962 | 1,427 | 4.9x | linear in diagnostics |

Against the 10,476-document corpus: `status --json` 259,453 bytes, `vault list --json`
5,934,668 bytes, `vault feature list --json` 199,581 bytes. `vault graph --json` did not
complete within 15 minutes and produced no output.

### The human surface is asymptotically bounded and the machine surface is not

Measured on disposable damaged copies of this vault at controlled damage fractions, which
isolates the divergence the clean corpus hides. `vault check all --json` returns 6,962 bytes
on the swept vault, 137,323 bytes at 5% of documents damaged, and 2,211,057 bytes fully
damaged. Over the same sweep the human render moves 50,320 to 65,320 to 69,119 bytes and
stops, because the render cap bounds it. At full damage the human reader sees 308 of 5,872
findings while the machine consumer receives all 5,872 - a 32x byte ratio on the identical
run.

This is the divergence stated as a curve rather than inferred from the contract: one surface
converges and the other does not, and the gap widens with exactly the condition the command
exists to detect.

`vault repair --dry-run --json` is worse per unit of damage: 850,927 bytes at 5% damage
against 4,479 bytes of human output, a 190x ratio for a preview that changes nothing. Its
envelope carries the same 372 findings five times over, so most of the payload is neither new
information nor a second copy but a fifth.

Exit codes narrow which callers are affected but do not bound anything.
`src/vaultspec_core/cli/vault_check_cmd.py:82`, `:168` and `:255` exit non-zero on errors
only; warnings and INFO diagnostics exit zero. All three damaged runs exited non-zero while
emitting the full report on stdout, so a caller treating non-zero as failure discards the
diagnosis it asked for, and a caller reading stdout regardless takes the full payload.

`vault graph --body --json` measures 16,118,440 bytes on the 1,222-document vault, higher than
the graph export without bodies.

### The derived-edge set is quadratic

`src/vaultspec_core/graph/derived.py:417` builds a list of every unordered pair of real nodes
via `itertools.combinations`, materialising the full pair set before any filtering, then emits
one record per pair carrying a non-zero signal. At 1,243 nodes this enumerates 772,003 pairs
and emits 23,499 edges totalling 6,218,016 bytes, 55% of the graph payload. Verified exactly
against feature size: a 15-node feature yields 105 derived edges, a 4-node feature yields 6 -
in both cases the count of pairs.

Growth is a sum of two terms with different exponents. Within-feature pairs are linear,
because documents per feature is fixed by workflow rather than by corpus size; cross-feature
pairs are quadratic. Compute is the harder limit: 10,476 nodes is roughly 54.9 million pairs,
and the command produced no output in 15 minutes against a corpus size the tool advertises
support for.

### Two multipliers apply across the whole surface

The MCP transport serialises every payload twice. The `convert_result` method in the vendored
SDK at `mcp/server/mcpserver/utilities/func_metadata.py:132` builds unstructured content and
structured content from the same object and returns both; `_convert_to_content` at `:562`
recurses through lists and emits one indent-2 text block per element. Any tool declaring a
Pydantic return type pays a flat 2x. The same function early-returns a caller-supplied
`CallToolResult` untouched at `:126`, validating structured content against the output schema
without synthesising a text copy.

Separately, all 53 `json.dumps` call sites across 23 CLI modules pass indent-2. Measured on
`vault list`: 497,405 bytes pretty against 369,067 compact, so 25.8% of the payload is
whitespace. On the more deeply nested graph payload the fraction approaches 30%.

### A narrowing flag can cost more than no flag

`src/vaultspec_core/cli/vault_cmd.py:650` evaluates the JSON branch and returns at `:682`,
before the metrics branch at `:687`. `vault graph --metrics --json` therefore returns the full
11,175,730-byte payload while the human form of the same flag returns 4,794 bytes. The agent
asking the narrower question pays 2331x more and receives no signal that its flag was
discarded. The 17-key metrics object it asked for is 5,186 bytes and is already computed
inside the payload it receives.

### The static surface is ungoverned prose

The nine-tool MCP surface serialises to 43,919 characters, roughly 12,693 tokens at the
measured 3.46 bytes per token for this codebase's JSON, and is re-sent every turn. Output
schemas are 26,785 of those characters, 61% of the total, because Pydantic lifts each result
model's full docstring - `Attributes:` blocks and reST markup included - into the schema
description. Tool descriptions add 7,599 characters and document a `ctx` parameter that
appears in no input schema. The `status` tool alone is 8,015 characters, 85% of it output
schema.

The regression guard at `src/vaultspec_core/mcp_server/tests/test_context_budget.py:58`
serialised only name, description and input schema, omitting output schema, and used indent-2
where the wire is compact. It measured 21,943 of 43,919 real characters, 50% coverage, and
passed against a 26,000 ceiling while roughly 22,000 characters grew ungoverned. The read-only
surface was covered at 25% and had no ceiling of its own.

### Size is not the only failure mode

Payloads that fit can still degrade a model by displacing signal. Measured information
density, useful bytes over wire bytes: a `find` feature row conveys 45 bytes of content in 298
wire bytes, 15%; `vault list` rows reach 35% after accounting for the absolute path prefix
repeated on every row, `name` derivable from `path`, and `tags` restating `doc_type` and
`feature`; `status` feature records carry roughly 100 null-valued bytes of 241. Graph node
records duplicate `tags`, `date`, `modified` and `related` between top-level fields and an
embedded frontmatter object, plus an `id` byte-identical to `name`, totalling 23% duplication.

### Correctness defects found during the audit

`src/vaultspec_core/mcp_server/tools/documents.py:868` declares a `limit` of 20 with no
bounds; a negative value reaches a Python slice and returns 128 of 129 rows instead of
erroring.

`src/vaultspec_core/mcp_server/tools/documents.py:732` requests feature rankings capped at 100
and reads the result with a zero default. `src/vaultspec_core/graph/api.py:816` scores every
node before slicing, so the cap is on output rather than computation, and a feature ranked
below 100 is indistinguishable from one scoring zero. All 129 features in this vault score
non-zero, yet 29 report a weight of zero; the lowest genuine score is 1.

### What was not investigated

Whether any MCP host dereferences the resource links that `find` rows carry, which determines
whether that field can be dropped or must be kept while inlined bodies are forbidden. Whether
the `Attributes:` docstrings feed a published documentation site: no Sphinx, mkdocs,
mkdocstrings, pdoc or griffe configuration exists in `pyproject.toml`, the justfile or
`docs/`, so no second consumer was found. Mutating verbs were not executed, so `install`,
`sync` and `migrations run` remain unclassified.

## Sources

- `src/vaultspec_core/vaultcore/checks/_base.py:206`
- `src/vaultspec_core/cli/rendering_shapes.py:47`
- `src/vaultspec_core/cli/rendering_shapes.py:283`
- `src/vaultspec_core/cli/_repair_render.py:21`
- `src/vaultspec_core/cli/_repair_render.py:201`
- `src/vaultspec_core/cli/status_cmd.py:53`
- `src/vaultspec_core/cli/status_cmd.py:138`
- `src/vaultspec_core/cli/status_cmd.py:216`
- `src/vaultspec_core/cli/vault_cmd.py:650`
- `src/vaultspec_core/cli/vault_cmd.py:687`
- `src/vaultspec_core/cli/vault_check_cmd.py:72`
- `src/vaultspec_core/cli/vault_check_cmd.py:82`
- `src/vaultspec_core/graph/derived.py:417`
- `src/vaultspec_core/graph/api.py:816`
- `src/vaultspec_core/vaultcore/orientation_rollup.py:210`
- `src/vaultspec_core/mcp_server/tools/documents.py:732`
- `src/vaultspec_core/mcp_server/tools/documents.py:828`
- `src/vaultspec_core/mcp_server/tools/documents.py:868`
- `src/vaultspec_core/mcp_server/tools/gateway.py:440`
- `src/vaultspec_core/mcp_server/tools/gateway.py:513`
- `src/vaultspec_core/mcp_server/tools/orientation.py:421`
- `src/vaultspec_core/mcp_server/results.py:87`
- `src/vaultspec_core/mcp_server/tests/test_context_budget.py:58`
- `mcp/server/mcpserver/utilities/func_metadata.py:126`
- `mcp/server/mcpserver/utilities/func_metadata.py:132`
- `mcp/server/mcpserver/utilities/func_metadata.py:562`
