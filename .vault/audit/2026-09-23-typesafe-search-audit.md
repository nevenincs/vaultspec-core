---
tags:
  - '#audit'
  - '#typesafe-search'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:8e251b2fdd12b9806b7e7d98ecefec008320b0184ac082d1d50e3da58314ff94'
related:
  - "[[2026-09-23-typesafe-search-plan]]"
---

# `typesafe-search` audit: `plan-close review of hosted vault search`

## Scope

Integrated review of plan `2026-09-23-typesafe-search-plan`, Steps S01 to S12, commits
`81c34bed..b8f75855`, against `2026-09-23-typesafe-search-adr` and its amendment notes
on `2026-07-09-mcp-tool-schema-adr` and `2026-08-01-mcp-read-only-adr`. The review
traced the search path from CLI and MCP through service, corpus, engine and transport,
the surfaces, the discovery guidance, and the canonical-base refactors. It ran against
the constraints of `2026-08-26-rag-search-exposure-adr` and
`2026-08-23-envelope-optimization-adr`. The CI result for PR 554 is included.

Result: `REVISION REQUIRED`. There are 4 high findings, 5 medium findings (including
CI) and 8 low findings.

Verified to hold:

- **Tool surface.** 11 normal tools and 5 read-only tools, `search` in both. It is
  registered unconditionally (`src/vaultspec_core/mcp_server/app.py:148`) and is
  invariant under the key state.
- **Credential.** The variable name is taken from the config registry
  (`src/vaultspec_core/search/_credential.py:51`).
- **Constants.** The endpoint and model are code constants
  (`src/vaultspec_core/search/_transport.py:108`,
  `src/vaultspec_core/search/_questions.py:52`).
- **Key never exposed.** The key is absent from the credential repr, from config logs
  and from transport messages.
- **Isolation from rag.** There is no rag import or call, and `uv.lock` is unchanged.
- **Filters.** Filters apply in code before any request
  (`src/vaultspec_core/search/_service.py:104`).
- **Excerpts.** Excerpts are verbatim at the reported file lines
  (`src/vaultspec_core/search/_corpus.py:309-328`).
- **Requests.** State is sanitised and every request is size-checked
  (`src/vaultspec_core/search/_transport.py:519-545`), and answers are validated.
- **Window.** The ranking window is not pageable
  (`src/vaultspec_core/core/windowing.py:84-93`).
- **CLI exit codes.** They match the reference catalogue.
- **Guidance routing.** Code search stays rag-only
  (`src/vaultspec_core/core/discovery_guidance.py:70`).
- **Snapshots.** The `.vaultspec/` snapshots equal the builtins.
- **Tests.** There are no mocks or skips, and the `typesafe` marker is deselected by
  default.

## Findings

### credential-gate | high | A cloned repository can enable hosted search for a globally installed core through its own .env

`src/vaultspec_core/search/_credential.py:77-94` reads the workspace `.env` when
`resolve_install_mode(root)` returns DEPENDENCY or DEV. That mode comes from the
repository's own committed `.vaultspec/workspace.json` or `pyproject.toml`
(`src/vaultspec_core/core/workspace_mode.py:1055-1078`). The reviewer reproduced
`configured=True, source=dotenv` from a scratch repository that declares vaultspec-core
in its dev group. The protection the ADR claims, "a cloned repository could supply
credentials to a globally installed tool", therefore does not hold.

### content-rejection | high | A search whose every request is refused reports ok and a false "nothing answers" verdict

`src/vaultspec_core/search/_transport.py:600-601` classifies every non-authentication 403
as a content block, JSON 403s such as `permission_error` included. With every request
refused, `search_vault` returned `ok`, `answered=False`, 0 hits and `unscored=6` after 16
requests. The CLI then printed "nothing in the vault answers this"
(`src/vaultspec_core/cli/vault_search_cmd.py:222-226`) and never surfaced the unscored
count. A query that itself trips the firewall produces the same result. A record whose
windows were only partly refused is ranked on partial text and is not counted as
unscored.

### adr-drift | high | The default page and the record grouping differ from the accepted ADR text

`src/vaultspec_core/search/_models.py:57` sets `DEFAULT_RESULTS` to 4 because of the
measured envelope budget. The ADR Constraint says 5.
`src/vaultspec_core/search/_questions.py:60-66` has reference and audit records share
one Choice and one per-group cap of 4 (`src/vaultspec_core/search/_engine.py:511-528`).
The evaluated prototype did this too, but the research and ADR text describe "4 per
type". The implementation matches what was measured; the records do not describe it.

### reply-ceiling | high | Excerpt caps count characters while the envelope budgets count bytes

`src/vaultspec_core/search/_models.py:57-71` caps excerpts in characters, and the size
test (`src/vaultspec_core/mcp_server/tests/test_search_tool.py:444-499`) uses ASCII
text. With CJK text at the caps and five-level heading paths, a 4-hit reply is 31,182
bytes (about 9,000 tokens against a 4,000-token budget). An 11-hit reply is 85,612 bytes
(about 24,700 tokens against the 10,000-token hard ceiling).

### ci-windows-ansi | medium | The status-row test fails on Windows CI because rich output keeps ANSI codes

PR 554 `Test: Library suite (Windows)` failed with 1 of 4,952 tests failing. The new
status test asserts the plain text `hosted search configured  source: environment`, but
the Windows output carries colour codes between the two parts. It is a test portability
defect; the product output is correct.

### rename-race | medium | The Windows rename-and-edit flake was exposed by this branch, not pre-existing

`test_no_deadlock_under_concurrent_rename_and_edit_load` failed 7 of 172 times on HEAD
and 0 of 142 times on main. Every failure is a `PermissionError(13)` from the unlocked
`old_path.read_bytes()` at `src/vaultspec_core/cli/edit_cmd.py:529`, racing an edit's
`os.replace`. That line is unchanged, but the branch's timing exposed it.

### duplicates | medium | Concepts this branch unified keep second homes

- `src/vaultspec_core/vaultcore/checks/modified_stamp.py:217-234` keeps its own
  frontmatter regex and `modified:` stamper.
- `src/vaultspec_core/plan/serialiser.py:178` renders frontmatter separately.
- `src/vaultspec_core/cli/vault_feature_cmd.py:252` re-declares `--date`.
- `src/vaultspec_core/search/_corpus.py:96` restates `"<!--"`.
- Excerpt clipping is implemented in both surfaces
  (`src/vaultspec_core/cli/vault_search_cmd.py:109-135`,
  `src/vaultspec_core/mcp_server/tools/search.py:187-206`).

### tool-args | medium | Tool parameter descriptions never reach the model

`src/vaultspec_core/mcp_server/envelope.py:89` `_CTX_ARG` expects 8-space indented
parameter docs, but `inspect.getdoc` dedents them to 4. The `ctx:` match therefore
swallows every later argument. The problem predates this branch, and it leaves the
`search` tool's `query` and `limit` undocumented.

### test-population | medium | Checkout-walking tests are marked unit

`src/vaultspec_core/vaultcore/tests/test_frontmatter_render.py:217-226` and
`src/vaultspec_core/vaultcore/tests/test_body_hash.py:245-249` glob the whole
repository. `dev/toolchain.py:55-66` requires such tests to be marked `repo`.

### rerender-flags | low | Two frontmatter output styles survive behind renderer flags

`rerender_frontmatter` in `src/vaultspec_core/vaultcore/parser.py` keeps two stamp
placements and two date quotings, so that existing files stay byte-identical.

### exec-log-blank | low | Appending a ledger row leaves no blank line after the heading

`src/vaultspec_core/vaultcore/exec_ledger.py:378` ends with `\n\n` on both main and HEAD.
`vault check --fix` repairs it on every append. The problem predates this branch.

### precommit-signal | low | install --upgrade warns about an unknown PrecommitSignal member

`src/vaultspec_core/core/resolver_repo.py:215-238` has no branch for `NOT_INSTALLED`.
The problem predates this branch and is outside the plan.

### cli-valueerror | low | Any ValueError from a search is reported as an invalid query

`src/vaultspec_core/cli/vault_search_cmd.py:283-284` catches every `ValueError` and exits
2 as if the query were invalid.

### blob-race | low | The blob hash can name a different file version than the excerpt

`src/vaultspec_core/search/_engine.py:859` hashes the file after the network stages, so
an edit in between leaves the hash and the line ranges describing different versions.

### oversize-line | low | One very long line fails every search that reads its record

A single line over about 99 KB makes a window exceed the request bound
(`src/vaultspec_core/search/_engine.py:595-603`). The whole search fails instead of the
record being left unscored.

### indented-fences | low | Code fences indented four or more spaces are no longer recognised

`src/vaultspec_core/vaultcore/markdown.py:96` follows the CommonMark rule for fence
indentation. The line scanner has no list context, so fences inside nested list items
are no longer protected, and `src/vaultspec_core/vaultcore/checks/markdown.py:94-97`
edits whitespace inside them. No such fence exists in this repository.

### boundary-names | low | A doc example and a test use this feature's vault names

`docs/CLI.md:1049` uses `--feature typesafe-search`, and
`src/vaultspec_core/mcp_server/tests/test_search_tool.py:444-447` builds stems from
this feature. Code and docs should not echo vault identifiers.

### re-review | low | The fix round resolves every high and medium finding; result PASS

The re-review covered commits `d6cfcb4c..a424b95a` against the findings above.

- **Resolved, 15 findings:** credential-gate, content-rejection, adr-drift,
  reply-ceiling, ci-windows-ansi, rename-race, duplicates, tool-args, test-population,
  cli-valueerror, blob-race, oversize-line, indented-fences, boundary-names and
  exec-log-blank.

- **Deferred as recommended, unchanged:** rerender-flags and precommit-signal.

- **Live evidence on the final code:**

  - The live tests pass 3 of 3.
  - Dev set: hit@1 0.90, excerpt 19/21.
  - Held-out set: hit@1 0.94, excerpt 12/18.
  - The rename race ran 40 serial runs with no failure.

  The research record carries the measurement.

- **CI wiring.** The merge gate now runs the live lane from a repository secret. No
  critical or high finding is open, so the result is `PASS`.

### reply-ceiling-root | medium | Each search hit's absolute resource URI grows the reply with the workspace path

`src/vaultspec_core/mcp_server/tools/search.py:226` puts `(root / path).as_uri()` on
every hit, and no byte cap covers it. With 11 worst-case CJK hits, a 26-character CJK
root reached 9,984 tokens, because URL encoding costs 9 bytes per CJK character. The
budget test's margin therefore depends on the machine's temp path.

### tool-surface-ratchet | medium | The tool-definition size ceilings were raised against the envelope ADR

`src/vaultspec_core/mcp_server/tests/test_context_budget.py:73` moves from 23,900 to
26,380 characters, and `:82` from 13,150 to 14,151.
`2026-08-23-envelope-optimization-adr` says the ceiling is never raised. The growth is
parameter documentation the tool-args bug had been dropping, so the surface was over
budget before this branch. About 7,600 tokens against a budget of 5,000.

### wire-mirrors | medium | The MCP search rows mirror the search dataclasses, and the two surfaces project hits differently

`SearchExcerpt` and `SearchUsageRow` in `src/vaultspec_core/mcp_server/tools/search.py`
repeat `Excerpt` and `SearchUsage` from `src/vaultspec_core/search/_models.py`. The CLI
`_hit_payload` and the MCP `_hit_row` give the same hit different keys and rounding.

### comment-markers | medium | HTML comment markers are still spelled out beside their canonical constants

`src/vaultspec_core/vaultcore/checks/annotations.py` and
`src/vaultspec_core/plan/parser.py:539` use `"<!--"` and `"-->"` literals.
`HTML_COMMENT_OPEN` and `HTML_COMMENT_CLOSE` are exported by
`src/vaultspec_core/vaultcore/markdown.py`.

### budget-constants | low | The envelope bytes-per-token ratio is declared twice

`src/vaultspec_core/search/tests/reply_budget.py:41` and
`src/vaultspec_core/mcp_server/tests/test_context_budget.py` each state 3.46.
`src/vaultspec_core/search/_transport.py` exports a `BYTES_PER_TOKEN` of 3.3 with
another meaning.

### credential-description | low | The config registry description omits the interpreter check

`src/vaultspec_core/config/config.py:506-510` describes the workspace `.env` as opened
by the install mode alone.

### block-units | low | Search blocks are bounded in characters by a byte constant

`src/vaultspec_core/search/_corpus.py:367` passes `EXCERPT_BYTES` as `max_chars`. A
multi-byte block can reach about 2,100 bytes, and the excerpt keeps only its first
700 bytes.

### fence-consumers | low | line_roles and non_prose_spans disagree on a list item opened before a comment

Take `- item <!--`, `note`, `-->`, then a fence indented four spaces. `line_roles`
closes the item at `-->` and reads the fence as text, so
`src/vaultspec_core/vaultcore/checks/markdown.py:96` edits inside it.
`non_prose_spans` protects the same fence.

### search-degradation | high | Hosted search declines to one ADR-only rag sentence whether or not rag exists

Without `VAULTSPEC_CORE_TYPESAFE_API_KEY` search returns `not_configured` (CLI exit 0);
on API failure it returns `unavailable` (CLI exit 1). Both carry one remediation
sentence (`src/vaultspec_core/search/_remediation.py:23-56`) built on `SEARCH_ADR`
(`src/vaultspec_core/core/discovery_guidance.py:57`), which names only
`vaultspec-rag search "<intent>" --type vault --doc-type adr`. Hosted search covers six
record types, and the sentence is emitted whether or not rag is provisioned, although
the companion probe already detects it
(`src/vaultspec_core/core/diagnosis/collectors_companion.py:41-65`). With no key and no
rag, nothing names `find`, `vault list` or grep. Core never calls rag, and
`src/vaultspec_core/search/_lexical.py` is a shortlist supplement, not a fallback.

### guidance-gate | high | Discovery routing is gated on a status field that readers cannot reach

`VAULT_SEARCH_ROUTING` (`src/vaultspec_core/core/discovery_guidance.py:70-73`), "When
`status` reports hosted search configured...", is copied into
`src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md:13-16`,
`skills/vaultspec-code-research/SKILL.md:16-18`, `skills/vaultspec-curate/SKILL.md:53`,
`skills/vaultspec-curate/references/reconciliation-playbook.md:26` and
`agents/vaultspec-docs-curator.md:37`. Read-only work and dispatched workers skip
status orientation, and targeted `status <feature>` omits `hosted_search` on CLI and
MCP, so they never see the gate. "Configured" is not liveness: a rejected key still
routes agents to hosted search first.

### output-handling | medium | The rules say nothing about reading search output or the unavailable branch

The builtins give no handling for search output: an excerpt as triage versus a whole
read, what `premise_conflict` means, or the "nothing in the vault answers this"
verdict. They have no branch for `unavailable`, and the no-semantic fallback
("discovery verbs and grep") conflicts with "do not lead with grep sweeps". The
`vaultspec-adr` skill names no coverage-check method, the code-reviewer persona never
searches for unlinked ADRs, and curate makes a rag health check a precondition for
decision recall.

### surface-drift | medium | The bundled reference misnames hit fields and the CLI JSON drops answered

`src/vaultspec_core/builtins/reference/cli.md:584` names a hit field `doc_type`; the wire
field is `type` (`src/vaultspec_core/search/_wire.py:46`), and `feature`, `date`,
`title` and `supporting` are missing. The vault search options table (`cli.md:576-581`)
renders as one paragraph. CLI `--json` `not_configured` omits `answered`
(`src/vaultspec_core/cli/vault_search_cmd.py:119`), while MCP returns `answered: false`
(`src/vaultspec_core/mcp_server/tools/search.py:164`).

### user-docs | low | README and the framework guide describe only rag for discovery

`README.md` and `docs/framework.md:95-101` name only vaultspec-rag. Hosted search setup
and the degradation chain appear only in `docs/CLI.md:968-1062,3278-3287` and
`docs/MCP.md:344-474`.

## Recommendations

- credential-gate: also require that the running interpreter is the workspace's own
  environment, and amend the credential constraint in the ADR to match.
- content-rejection:
  - Classify only non-JSON 403s as content rejections.
  - Report `unavailable` when every record is refused.
  - Count partly read records as unscored.
  - Never state that nothing answers while records went unscored, and surface the
    count.
- adr-drift: amend the ADR and research text to the measured values, the default of 4
  hits and the shared reference and audit group.
- reply-ceiling: bound excerpts, titles and sections by encoded bytes, and clip once
  inside the search package rather than in each surface.
- ci-windows-ansi, rename-race, cli-valueerror, blob-race, oversize-line,
  test-population, tool-args, exec-log-blank, indented-fences, boundary-names, and the
  surface-clipping, `<!--`, `--date`, stamper and plan-serialiser items under
  duplicates: fix within the plan's scope. None needs a new decision.
- rerender-flags: a follow-on ADR must decide one canonical date quoting and stamp
  placement, and whether existing documents are rewritten to it.
- precommit-signal: outside this plan; record it for the owning feature.
- reply-ceiling-root: drop the per-hit resource URI from search rows. The relative path
  and the blob hash already locate the version, and `find` still returns the URI.
- tool-surface-ratchet: a follow-on ADR must decide between restating the
  tool-definition budget and trimming parameter documentation back under the old
  ceiling.
- wire-mirrors, comment-markers, budget-constants, credential-description, block-units
  and fence-consumers: fix within the plan's scope. None needs a new decision.
- search-degradation: resolve the next step in the search backend, from the companion
  probe and the requested record types: a rag vault search over those types when rag
  is provisioned, else `find` or `vault list` plus grep. Carry it as a typed part of the
  result. This refines the fallback decision of `2026-09-23-typesafe-search-adr`.
- guidance-gate: make the guidance state-free. Vault questions go to `search`; when it
  declines, run what its reply names. No `status` gate.
- output-handling: add output handling, the `unavailable` branch and a degraded-mode
  grep carve-out to the discovery rule, and a coverage-check method to the ADR skill
  and the code-reviewer persona. Keep the ADR listing mandatory beside search until
  hosted-search recall is measured.
- surface-drift: render CLI and MCP from one backend result with identical fields, and
  fix the reference generator inputs. No new decision beyond the ADR amendment.
- user-docs: add hosted search and the degradation chain to `README.md` and
  `docs/framework.md`.
