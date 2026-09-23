---
tags:
  - '#audit'
  - '#typesafe-search'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:6310468714b54eb645cf2a77eadcd54e67b9b59de5f77af95df1f6da8a296715'
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

### discovery-fallback-close | high | The plan-close review of the discovery fallback finds two red gates; result REVISION REQUIRED

The review covered plan `2026-09-23-discovery-fallback-plan`, S01 to S05, commits
`ba5dd259`, `2ee3d5ed`, `84c4098a`, `ccf05dcb`, `bd4abc26` and `9bd7e145`, against the
discovery-fallback amendment of `2026-09-23-typesafe-search-adr` and the plan's related
decisions. It traced a declined search from the service through `outcome_fields` to CLI
text, CLI `--json` and MCP `search`, both status surfaces, the guidance constants
through the builtins to their `.vaultspec/` copies, and the user docs against the code.

Result: `REVISION REQUIRED`. There are 2 high, 3 medium and 2 low findings below.

Gates, run on a clean checkout of `bd4abc26`:

- pytest over `search`, `mcp_server/tests`, the CLI vault search, status and reference
  tests, `test_discovery_guidance` and `dev/guards`: 698 passed and 1 failed, the
  docs-bare-commands finding.
- `just check-markdown` fails on the plan's own ledger, the ledger-note-escaping
  finding.
- On `1d2adb31`, after the environment-variable centralisation lane committed its move
  of the credential into `config/`, the search, capability, MCP search, CLI search,
  status and guidance tests pass (165). The next-step wiring survives that move:
  `_remediation.py` and `_capability.py` now read the variable name from the config
  registry, and `next_step` is unchanged.

Verified to hold:

- **Backend-resolved fallback.** `next_step`
  (`src/vaultspec_core/search/_remediation.py:67-90`) resolves a typed `NextStep` from
  the companion probe and the requested types. `SearchOutcome.__post_init__`
  (`src/vaultspec_core/search/_models.py:335`) makes a decline without a step, or a
  ranked page with one, unrepresentable.
- **Search parity.** CLI `--json` `data` and the MCP result are both `outcome_fields`
  (`src/vaultspec_core/search/_wire.py:74`), and
  `test_the_wire_is_the_search_packages_one_projection` holds them equal. `answered` is
  always present. Type validation lives in `src/vaultspec_core/search/_filters.py`,
  and the surfaces only map `UnsearchableTypeError` and `InvalidQueryError` to their own
  error types.
- **rag exposure.** The probe reads `.mcp.json` and distribution metadata only. No rag
  import or call was added.
- **State-free guidance.** No builtin rule, skill or persona names TypeSafe, a key or a
  `status` gate. The routing sentence lives in the discovery rule alone, the ADR
  listing is its own mandatory step, and the `.vaultspec/` copies equal the builtins.
- **Reference.** The generated reference lists the wire hit fields and renders the vault
  search options as a table, and the drift tests pass.
- **Boundaries.** The reviewed code and tests cite no vault record and add no
  suppressions, skips or mocks.

### docs-bare-commands | high | The S05 user docs teach bare CLI commands and fail the CLI language guard

`dev/guards/test_cli_language_contract.py:262` fails on `docs/framework.md:97`, `:108`
and `:110` (`vault search`, `vault list`), `docs/MCP.md:686` (`status --json`) and
`README.md:97` (`vault search`). The guard requires the `vaultspec-core` entry point on
every runnable snippet. The S05 verify row
(`.vault/exec/2026-09-23-discovery-fallback/2026-09-23-discovery-fallback-ledger.md:86`)
ran only `just framework-reference-check`, so the guard never ran on S05. The S04 note
(`:115`) recorded the failure without routing it.

### ledger-note-escaping | high | The ledger writer emits note text raw, so check-markdown fails on a machine-owned ledger

`just check-markdown` fails on the S03 note
(`.vault/exec/2026-09-23-discovery-fallback/2026-09-23-discovery-fallback-ledger.md:114`):
mdformat escapes the underscores in `search/_models.py` and `search/_credential.py`,
which the note carries as plain text. `format_note`
(`src/vaultspec_core/vaultcore/exec_ledger.py:284-286`) joins free text unescaped.
`format_row` (`:278-279`) backticks every cell, and `8d46b5e2` fixed only the
blank-line layout. Any note that names a private module or holds `*`, `_` or `<` leaves
a file the markdown gate refuses, and the file may not be hand-edited. The working tree
holds an uncommitted hand-escape of that line from another session. It clears the gate,
but the writer defect remains. No Step of this plan owns `exec_ledger.py`.

### status-companion-parity | medium | MCP status omits the companion record the CLI carries, an exception the amended ADR does not record

CLI `status --json` spreads `discovery_fields` (`hosted_search` and `companion`,
`src/vaultspec_core/cli/status_cmd.py:285-297`). MCP `StatusResult` carries
`hosted_search` alone, read through `hosted_search_config` directly
(`src/vaultspec_core/mcp_server/tools/orientation.py:28,542`) rather than
`discovery_capability`. The amendment's thin-surfaces bullet
(`.vault/adr/2026-09-23-typesafe-search-adr.md:229`) promises identical fields, and S01
names both status surfaces.

The reason is sound: the companion record costs 439 tool-definition characters against
a ceiling `2026-08-23-envelope-optimization-adr` says is never raised. The companion
only decides the fallback, which reaches an MCP agent as `next_step`, so nothing an
agent acts on is lost. `docs/MCP.md` documents the difference. The reason is recorded
only in a ledger note (`:112`), which is not a home for decisions. The ADR contradicts
the code as shipped.

### status-companion-prose | medium | CLI status words its own discovery fallback, contradicting the canonical routing

`_companion_line` (`src/vaultspec_core/cli/status_cmd.py:252-255`) prints "not
provisioned - use find and grep for discovery". This is guidance authored in a surface.
It sends vault questions to find and grep past `search`. It differs from
`DISCOVERY_FALLBACK` (`src/vaultspec_core/core/discovery_guidance.py:47-50`, a targeted
grep for code). It also names the MCP verb `find` on a CLI surface. The plan's
verification forbids status logic beyond rendering in `cli/`.

### verdict-vocabulary | medium | The discovery rule keys reply handling to terminal sentences that MCP replies never carry

`src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md:34-37` and
`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:15-16` quote "nothing in the
vault answers this" and "no record that was read answers this". Those are
`SearchVerdict.sentence` (`src/vaultspec_core/search/_models.py:145`), printed only by
CLI text. MCP and `--json` carry `verdict` as `nothing_answers` or `none_read_answers`
(`src/vaultspec_core/search/_wire.py:94-95`). An MCP agent must map value to sentence
unaided. No guard in `src/vaultspec_core/tests/test_discovery_guidance.py` ties the
quotes to the enum, so rewording a sentence silently orphans the rule.

### surface-wording | low | Surfaces still author outcome wording the backend owns elsewhere

The MCP summary derives "answered" or "not answered" from `answered`
(`src/vaultspec_core/mcp_server/tools/search.py:184`), not from `verdict`. A
`none_read_answers` page therefore logs "not answered", while the CLI prints "no record
that was read answers this". CLI text authors the premise note, the missing-passage line
and the unscored line (`src/vaultspec_core/cli/vault_search_cmd.py:122,130,165`). They
are terminal-only, so wire parity holds.

### next-step-scope | low | The next step keeps the type filter but drops the feature and date filters

`next_step` (`src/vaultspec_core/search/_remediation.py:67`) and `_declined`
(`src/vaultspec_core/search/_service.py:74`) carry only the types. A declined
`--feature x` search therefore names a vault-wide rag search or listing, though rag
takes `--feature` and `--date` and `vault list` takes `--feature`. The amendment asks
only for types, so this conforms.

### discovery-fallback-rereview | low | The fix round resolves both high findings and every medium and low one; result PASS

The re-review covered commits `1b536b3b`, `03959c68`, `10a18f38`, `571a188c`,
`080df9e6`, `293f3beb` and `26d590bd` against the plan-close findings above, the
discovery-fallback amendment of `2026-09-23-typesafe-search-adr`, and the envelope and
tool-schema decisions (`2026-08-23-envelope-optimization-adr`,
`2026-07-09-mcp-tool-schema-adr`). It re-traced only changed behavior: the result-schema
change through every tool that publishes it, the wording module into both search
surfaces, the next-step filters into the command, the note writer against mdformat, the
verify flag through the backend, CLI and MCP, and the rewritten builtins against their
`.vaultspec/` copies.

Result: `PASS`. No critical or high finding is open. There are 2 medium and 4 low
findings below.

Gates, run on a clean export of `26d590bd` so peer sessions' uncommitted work was
excluded:

- pytest over `search`, `mcp_server` (including the tool-size guard in
  `test_context_budget.py`), the CLI status, vault search, exec and reference tests, the
  vaultcore exec ledger, fold and recovery tests, `test_discovery_guidance` and
  `dev/guards`: 886 passed.
- `just check-markdown`: 3 ok, run on the worktree, whose Markdown matched `HEAD`.
- `just check-type-strict`: 0 errors over 701 files.

Resolved, with evidence:

- **docs-bare-commands.** `1b536b3b` spells the entry point in `README.md`,
  `docs/framework.md` and `docs/MCP.md`, and `dev/guards` passes.
- **ledger-note-escaping.** `format_note`
  (`src/vaultspec_core/vaultcore/exec_ledger.py:296`) sets any word holding a
  markdown-significant character as a code span in mdformat's own form. A probe of 20
  notes found each one idempotent under re-rendering and accepted by mdformat. The inputs
  included private paths, `*`, `<`, `&`, `~~`, links, unbalanced and doubled backticks,
  and backslashes. Existing ledgers are never re-rendered on append (`exec_log.py:325`),
  so they cannot churn. `check-markdown` passes.
- **status-companion-parity.** MCP `status` now spreads `discovery_fields` from
  `discovery_capability` (`src/vaultspec_core/mcp_server/tools/orientation.py:310`).
  This matches the amendment's thin-surfaces bullet, so no ADR amendment is needed.
  `test_search_tool.py` holds both status surfaces' keys equal on a provisioned
  workspace.
- **status-companion-prose.** `_companion_line`
  (`src/vaultspec_core/cli/status_cmd.py:252`) states provisioning only.
- **verdict-vocabulary.** The discovery rule and the ADR skill quote each negative
  verdict with its wire value. `test_discovery_guidance.py:189,197` reads the builtin
  text against `SearchVerdict`, so a reworded sentence fails the guard. The guard is not
  tautological.
- **surface-wording.** `src/vaultspec_core/search/_wording.py` is the one home for
  outcome labels, the unscored note, the premise note and `NO_PASSAGE`. The CLI and MCP
  summary import them. What remains in `cli/vault_search_cmd.py` is layout: the hit
  header, the `also` locator line and styles. It carries no outcome wording.
- **next-step-scope.** `_scope_flags` (`src/vaultspec_core/search/_remediation.py:68`)
  admits a feature only through `normalize_feature_tag`, which requires kebab-case, and a
  date only as `normalize_vault_date` re-renders it in `yyyy-mm-dd` form. Neither can
  place arbitrary text in the command. A malformed filter is dropped, and
  `test_a_malformed_filter_never_reaches_the_command` covers the drop. `vault list` takes
  both flags through the shared `DateFilterOption`, and `vaultspec-rag search --help`
  lists `--feature` and `--date`.

Verified to hold:

- **Result schemas.** `_collapse_nullable`
  (`src/vaultspec_core/mcp_server/envelope.py:330`) reaches only `LeanResult` and
  `LeanShape`, so it changes only the `status`, `check` and `search` schemas.
  Every other tool's schema is unchanged. Synthetic replies with every nullable field
  null or omitted were built through `_structured` and validated with Draft 2020-12
  against each tool's published schema: status rollup and trace, `check` with a pathless
  finding, and search `ok`, `not_configured` and `unavailable`. All 8 validate. Required
  nullable keys (`next_open_step`, `latest_activity`, `record_stem`, `CheckFinding.path`,
  and `CompanionCapability.mode` and `version`) keep `null`. The in-memory MCP client in
  the tool tests also validates each reply against its output schema. Both ceilings were
  lowered, not raised, as the envelope ADR's ratchet requires.
- **Builtins.** No builtin gates on `status` or runtime state. The `.vaultspec/` copies
  of all ten touched files equal the builtins at `26d590bd`.
- **Boundaries.** The fix round's code and tests cite no vault record. They add no
  suppressions, skips or mocks.

### log-verify-parity | medium | MCP log takes one verify per call while the CLI flag is repeatable

`LogRequest.verify` (`src/vaultspec_core/vaultcore/exec_log.py:76`) holds a tuple, and
`vault exec log --verify` (`src/vaultspec_core/cli/exec_cmd.py:245`) is repeatable.
MCP `log` still takes `verify: str | None`
(`src/vaultspec_core/mcp_server/tools/exec.py:93,128`), although `rows` and `notes` on
the same tool are lists. An agent can reach the same ledger with one call per check,
because appends are idempotent. The capability is therefore reachable, but the two
surfaces take different shapes. That breaks the user's parity mandate. The exception is
recorded only in the S07 ledger note, which is not a home for decisions. The
status-companion-parity finding was closed the same way.

### adr-listing-exemption | medium | The discovery rule exempts approved plans from the ADR listing the amendment keeps mandatory

`src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md:25` (`10a18f38`) says
that under an approved plan the plan's linked decisions satisfy the decision listing.
The amendment's "ADR listing stays" bullet
(`.vault/adr/2026-09-23-typesafe-search-adr.md:231`) keeps the listing mandatory beside
search until hosted-search recall is measured. It grants no exemption. The change was a
friction fix outside the first review's recommendations, and the rule now relaxes an
accepted decision's term without an amendment.

### listing-dedup-scope | low | Running a declined search's listing once as step 4 can narrow the decision listing

The rule (`vaultspec-discovery.builtin.md:42`) merges a declined search's
`vaultspec-core vault list` next step with step 4 ("run it once"). Since `080df9e6`,
that next step carries the request's types, `--feature` and `--date`
(`_remediation.py:88`). A declined `--type research --feature x` search then names
`vaultspec-core vault list research --feature x`. Run once as step 4, it replaces the
all-feature `vault list adr` that step 4 requires. Two fixes, each Step-local, interact.

### companion-null-vs-absent | low | A failed companion probe is null on the CLI but an omitted key on MCP

`discovery_fields` (`src/vaultspec_core/search/_capability.py:115`) yields
`"companion": None`. CLI `status --json` sends it as null. The MCP envelope prunes the
optional null, and its schema now publishes no null branch. `docs/MCP.md:690` says the
tool returns `null`. `test_status_rollup_carries_the_backend_discovery_record`
(`mcp_server/tests/test_orientation_tools.py:109`) reads keys with `payload.get`, so the
test cannot tell an absent key from a null one. This affects only the probe-failure
path.

### schema-null-invariant | low | Schema omissibility and null pruning are derived separately with no guard tying them

The schema drops a null branch when the key is not in the schema's `required`
(`envelope.py:206`). The wire prunes a null when the field is not `is_required()`
(`envelope.py:414`), and only on models it reaches through lists or directly. No result
model today is aliased or nested in a dict or dataclass, so every current reply
validates. A future model that is aliased or nested that way would publish no null
branch and still send null. Schema-validating hosts would then refuse the reply, and no
test would notice first.

### ledger-hand-repair | low | The existing S03 ledger note was repaired by hand, not through the writer

`1b536b3b` hand-escaped `search/\_models.py` and `search/\_credential.py` in the
machine-owned ledger
(`.vault/exec/2026-09-23-discovery-fallback/2026-09-23-discovery-fallback-ledger.md:142`).
The recommendation named the writer or `vault check --fix`. The line passes the gate. If
it were ever re-rendered through `format_note`, as `exec_fold.py:215` re-renders notes,
the backslashes would become literal characters inside a code span. No path re-renders
this ledger today, so nothing else is needed.

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
- docs-bare-commands: spell `vaultspec-core vault search`, `vaultspec-core vault list`
  and `vaultspec-core status --json` in `README.md`, `docs/framework.md` and
  `docs/MCP.md`. Re-verify S05 with `dev/guards` and `check-markdown`. This reopens S05.
- ledger-note-escaping: make `format_note` in
  `src/vaultspec_core/vaultcore/exec_ledger.py` emit text the markdown gate accepts, and
  test it with a note naming `search/_models.py`. Repair the existing line through the
  writer or `vault check --fix`, not by hand. This needs an in-scope correction Step
  added with the plan verbs, because no Step owns the file.
- status-companion-parity: amend the thin-surfaces bullet of
  `2026-09-23-typesafe-search-adr`. Identical fields hold for `search`; MCP `status`
  carries `hosted_search` alone under the tool-definition budget, and the companion
  reaches agents as `next_step`. The amendment needs user authorization. Separately,
  read MCP status through `discovery_capability(...).hosted_search`, so both status
  surfaces share one backend entry point (S01 scope).
- status-companion-prose: drop the advice clause from `_companion_line` and state
  provisioning only, as `_hosted_search_line` does, or render a sentence the search
  package owns. This reopens S01.
- verdict-vocabulary: name the wire value beside each quoted sentence in the discovery
  rule and the ADR skill. Add a guard to `test_discovery_guidance.py` that the rule
  carries each negative `SearchVerdict` value and sentence, then sync. This reopens S04.
- surface-wording: have the MCP summary word `verdict`. Consider moving the premise and
  unscored sentences beside `SearchVerdict.sentence`. No new decision is needed.
- next-step-scope: carry the feature filter, and the date filter for rag, into
  `NextStep.command`. No new decision is needed.
- log-verify-parity: make MCP `log` take `verify: list[str] | None`, as it takes `rows`
  and `notes`, and pay for the schema bytes within the ratchet. If the budget cannot
  absorb that, record the single-verify exception in the governing ADR with user
  authorization. The in-scope owner is S07, which touched `mcp_server/tools/exec.py`. No
  new decision is needed for the list form.
- adr-listing-exemption: either drop the approved-plan exemption from the discovery rule
  and sync, or amend the "ADR listing stays" bullet of `2026-09-23-typesafe-search-adr`
  to grant it. The amendment needs user authorization. Owner: S04.
- listing-dedup-scope: limit the "run it once" merge to a next step that lists `adr` with
  no feature or date filter, or drop the merge. Owner: S04.
- companion-null-vs-absent: correct `docs/MCP.md` to say the key is omitted when the
  probe failed, or send the same representation on both surfaces. Make the parity test
  compare key presence. Owner: S01 and S05.
- schema-null-invariant: add a guard that builds each `LeanResult` with every nullable
  field `None`, passes it through `_structured`, and validates it against the tool's
  published schema. Owner: S01. No new decision is needed.
- ledger-hand-repair: record only; no action.
