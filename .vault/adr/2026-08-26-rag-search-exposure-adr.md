---
tags:
  - '#adr'
  - '#rag-search-exposure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6de9309d0c3456cbc21ef562b3e705b632a97b993fe81581d9e748fbc1b15278'
related:
  - '[[2026-08-26-rag-search-exposure-research]]'
---

# `rag-search-exposure` adr: `Expose rag capability, not rag search, from vaultspec-core` | (**status:** `proposed`)

## Problem Statement

`vaultspec-core` exposes no semantic search and never has. There is no search
tool in `mcp_server/tools/`, no search command in `cli/`, no HTTP client, and no
`vaultspec_rag` import anywhere in the package. `find`
(`mcp_server/tools/documents.py:942`) accepts `feature` / `type` / `date` /
`body` / `limit` and no query string at all - it is a filtered directory
listing, not a search.

The coupling that does exist is prose. Eight builtin agent documents instruct
agents to shell out to `vaultspec-rag search "<concept>" --type code` and
`--type vault --doc-type adr`, and six of them carry a hand-written fallback
clause for when rag is absent. That coupling is unversioned, untestable,
invisible to the MCP host, and cannot carry rag's grammar.

The gap is now measurable. rag 0.4.4 exposes `search_vault`,
`search_codebase`, `search_documents`, and `search_combined` (22 parameters),
with a filter-token grammar in `search/_parsing.py` covering `type: feature: date: tag: lang: path: func: class: nodetype: intent: status: exclude: only: include:`, plus `intent` ranking profiles, `like_ids` / `unlike_ids` relevance
feedback, `prefer`, `dedup_locales`, and extractor filters. rag's own CLI
exposes none of `intent`, the relevance-feedback ids, or the domain filters -
they are MCP-only or inline-token-only. Core's prose drives the CLI, so core's
advertised path is structurally a tier behind rag and cannot catch up.

Meanwhile core's only declared knowledge of rag is `vaultspec-rag[mcp]>=0.3.8`
in the PEP 735 `dev` dependency group (`pyproject.toml:110`) - never published,
never a runtime constraint, and one minor version stale. Core cannot observe
rag's version at runtime, and `doctor` has no rag probe.

## Considerations

- The dependency graph runs rag to core, not core to rag. rag vendors core in
  its venv, ships `vaultspec-core.builtin.json`, and imports core's
  `write_package_declaration` directly (`vaultspec_rag/commands/_mode.py:232`).
  `workspace_mode.py:168` already maintains a back-compat constant *for rag
  consumers floored on core 0.1.38*. Core cannot take a runtime dependency on
  rag without inverting an established direction and creating a release cycle.

- The per-package floor mechanism exists and is already used - by rag, on rag's
  own entry. The schema 2.0 `packages` map carries `minimum_version` per
  distribution with a skew handshake (`workspace_mode.py:979-1010`). Crucially
  the floor on a distribution's entry is an input to *that distribution's* gate,
  so the map is a place packages declare constraints about themselves, not about
  each other.

- Core's MCP contract is currently synchronous, filesystem-local, root-anchored
  via `_isolated_context`, and cannot fail for environmental reasons. Every rag
  search tool is an async call over a discovered loopback port into a stateful
  service with a qdrant runtime, GPU admission and borrow leases, job manager,
  watchers, and service eviction and residency. Proxying folds that entire
  failure surface into a contract that presently has none.

- rag hard-refuses a foreign release on every data-plane call
  (`mcp/_tools.py:199-223`), by design, because an unrecognised request field
  would otherwise be dropped silently and the answer computed against a
  different candidate set behind a 200. A core proxy would therefore sit in
  front of a client that fails closed on skew, surfacing a fatal error core has
  no ability to resolve - while core's own rag floor sat stale at `>=0.3.8`
  against rag 0.4.4 with nothing consuming it.

- rag deliberately exempts `stop`, `status`, `doctor`, `logs`, and `jobs` from
  that release gate (`serviceclient/_compat.py:217-221`), because they are how
  an operator observes and resolves a mismatch. That makes
  `vaultspec-rag server doctor` the one rag surface designed to answer under the
  degraded conditions where a core-side liveness probe would be least
  trustworthy.

- Every rag search tool accepts `project_root: str | None`. Core's tools are
  root-bound by construction; forwarding that parameter would hand a caller a
  documented way to redirect a core tool outside its workspace root.

- `get_code_file(path)` is an unbounded arbitrary-file read by path. Core's own
  body path is deliberately bounded - `body` tiering, `_FULL_BODY_MAX_ROWS`, and
  explicit `body_bytes` / `body_truncated` accounting so a caller knows what it
  did not receive.

- Search results are third-party text: vendored dependencies, generated code,
  docs, locale files. Core's tools today only ever return vault documents the
  user authored. rag's noise-domain profile demotes those sources for relevance,
  not as a trust boundary.

- The loopback transport is better defended than it first appears and the risk
  must be stated precisely. `_loopback_http.py` pins 127.0.0.1, disables proxy
  inheritance, and refuses redirects. But `resolve_data_plane_service` takes the
  port *and* the version it validates from the same on-disk discovery payload
  (`serviceclient/_compat.py:226-232`), so the release check defeats an outdated
  peer, not a forged one: a tampered or stale pointer supplies both the redirect
  and the version that blesses it. The trust root is discovery-file integrity,
  not the port. This is a real concern about whoever opens that socket - and a
  decisive reason for core not to become a second such caller.

- Hosts cache an MCP server's tool list at connect. Any surface that varies with
  what happens to be installed is a surface the host can hold stale.

- MCP tool budget is a real constraint. rag already ships
  `vaultspec-rag.builtin.json` and core already syncs companion MCP entries
  (`core/mcps_mode.py:175`). A host that wants search can run both servers today;
  a proxy adds a hop and a second copy of thirteen tools.

- The `vaultspec-rag` entry in `.mcp.json` is a shape **core** owns, not rag.
  `render_launch_for_mode` (`core/mcps_mode.py:60-98`) is the single launch
  comparator for every core-provisioned package, parameterized by distribution
  and module precisely so a companion substitutes through it rather than
  through a per-package table; rag's mode-neutral builtin only names its own
  package and module. A probe that reads that entry is therefore reading core's
  own rendered output, interpreted by core's own comparator. This is what makes
  the zero-coupling claim hold rather than merely sound good: the only rag-
  authored artifact anywhere on the probe's path is a version string.

## Considered options

- **Keep the prose coupling (status quo).** Rejected. It is the one option with
  no version story, no error contract, and no test. Eight files drift
  independently, and the fallback clause is already the entire degradation
  design.
- **Full proxy: core registers search tools that forward to rag.** Rejected on
  coupling, robustness, and security together. It inverts the dependency
  direction, forces core to validate a schema it does not own and cannot pin,
  imports rag's whole runtime failure surface into a contract that currently
  cannot fail environmentally, and inherits `project_root` redirection plus an
  unbounded file read. Core would advertise thirteen tools that are wrong
  whenever rag is absent, stale, or down.
- **Thin CLI passthrough (`vaultspec-core search` shelling to `vaultspec-rag`).**
  Rejected. It reaches only rag's CLI, which is the impoverished half of rag's
  surface - no `intent`, no relevance feedback, no domain filters. It codifies
  today's capability gap in shipped code instead of prose, which is worse: now
  it has a version and a test suite asserting the wrong thing.
- **Conditional registration: register search tools only when rag is detected at
  server start.** Rejected, and it is the strongest rival. It makes core's tool
  schema environment-dependent, so two workspaces on the same core version
  present different surfaces - the precise reproducibility property the
  install-mode machinery exists to guarantee. Hosts cache the tool list at
  connect, so a rag installed or removed mid-session yields a surface that is
  confidently wrong in both directions. It also does not remove any of the
  security items above; it only makes them intermittent, which is harder to
  audit than always-on.
- **Extract the filter grammar into a shared schema package both depend on.**
  Rejected. It makes the cycle explicit and forces lockstep releases on exactly
  the axis that already drifted (rag 0.3.8 to 0.4.4 with core's floor
  stationary). The grammar is rag's product surface; a shared package would
  freeze rag's ability to evolve it.
- **Capability probe, generated guidance, advisory floor, and a text filter on
  `find`. Chosen.** Core reports what rag *is* rather than proxying what rag
  *does*. Coupling stays one-directional and data-shaped, the tool surface stays
  fixed and root-bound, and the non-rag path stops being "use grep".

## Constraints

- Core declares no runtime or published-extra dependency on `vaultspec-rag`. The
  `dev` dependency-group entry stays dev-only.

- **Core calls no rag API, imports no rag module, and opens no socket to rag's
  service.** The probe reads only surfaces core already owns: the workspace
  `.mcp.json` entry and installed-distribution metadata. Core knows nothing of
  rag's request or response schema, so there is no schema to drift against.
  Liveness and index freshness are rag's to report, through
  `vaultspec-rag server doctor`, and core points at that command rather than
  reimplementing it.

- Core's MCP tool list is a pure function of core's version. It never varies
  with rag's presence, version, or service state.

- Core never forwards a caller-supplied `project_root` to any rag surface, and
  never exposes a path-addressed read that is not bounded the way `find`'s body
  tiering is bounded.

- The probe is read-only and non-actuating: it observes configuration and
  metadata, and never starts, indexes, evicts, or reindexes. It must not be
  usable as a remote trigger for rag work.

- The probe never places rag-derived document *content* into core's output. It
  returns presence, declared mode, version, and a floor verdict only. Search
  text stays on rag's own MCP channel, where the host attributes it to rag.

- The probe is local and total: every stage degrades to a reported `unknown`,
  never an error and never a hang. Because nothing on the path is a network
  call, there is no timeout, no retry policy, and no partial-outcome state to
  design. `status` and `doctor` must remain usable with rag missing,
  half-provisioned, or mid-reindex.

- Version comparison is advisory. A rag below core's declared floor produces a
  warning and a fix hint; it never refuses a core operation. Core has no
  standing to block on a package it does not depend on.

- The floor is declared in one place and consumed everywhere. No second
  hardcoded version literal.

- Agent guidance about rag is generated from the probe's vocabulary, not
  hand-authored per agent.

- No doubles, no runtime patching, no pass-through shims, and no re-exports.
  The repository already guards the first of these
  (`dev/guards/test_test_suite_quality.py`); the rest are the same principle
  applied to source. Concretely, for this feature:

  - The probe takes its package and floor as parameters, so every reported
    state is reachable from real inputs - a real `.mcp.json`, a really
    installed distribution, and real version strings. Needing to patch the
    version lookup to reach a state would have been evidence the seam was in
    the wrong place, not a reason to patch.
  - The capability is addressed at exactly one place. When the attribute
    ceiling moved it onto `HomeDiagnosis`, the fix was to repoint its reader,
    not to leave a forwarding property on the outer class: two addresses for
    one piece of state hide where the data actually lives.
  - Annotation-only imports stay under `TYPE_CHECKING`, so a module never
    becomes a second importable path to a name another module owns.

## Implementation

1. **Capability probe (config and metadata only).** A single read-only collector
   under `core/diagnosis/` resolves two things and stops: whether a
   `vaultspec-rag` entry exists in the workspace `.mcp.json` and what install
   mode it declares - reusing `read_mcp_servers` and `render_launch_for_mode`
   rather than a second launch-shape table - and the installed distribution's
   version from package metadata. Each resolves to `unknown` independently, so
   "no entry", "entry but no distribution", and "both present" are distinct
   reported states. No socket, no rag import, no rag API.

   One limitation found in implementation: the shared `observed_mcp_mode`
   comparator re-renders the expected argv without a `tool_spec`, so it expects
   `uvx --from vaultspec-rag` and cannot match the
   `uvx --from vaultspec-rag[mcp]` that rag actually deploys. The probe falls
   back to a structural rule - `uvx` is tool mode, `uv` is dependency mode -
   which carries no per-package knowledge and degrades to a coarser answer
   rather than a wrong one. The shared comparator is left alone: it feeds
   mode-mismatch signalling, and widening it would change what counts as drift.

1. **Surface it as data.** The probe's result becomes a field on `status` and a
   section in `doctor`, carrying presence, declared mode, version, and the
   floor verdict. Where liveness matters, the rendered output names
   `vaultspec-rag server doctor` as the authority instead of guessing at it.
   The probe carries no document text. The row is never error-weighted and must
   not move the doctor's exit code.

1. **Core-local advisory floor. Core does not write it into the packages map.**
   The floor is one constant in core, consumed only by core's own rendering. The
   `dev` group's `vaultspec-rag[mcp]` specifier is held against the same constant
   by test so the two cannot disagree.

   The obvious-looking alternative - writing `minimum_version` onto the
   `vaultspec-rag` entry via the existing `PackageDeclaration` machinery - is
   rejected on inspection, and this is the sharpest coupling trap in the design.
   rag imports core's `write_package_declaration` and writes *its own* entry
   (`vaultspec_rag/commands/_mode.py:231-235`), explicitly reading back and
   preserving whatever `minimum_version` it finds. That entry is rag's, and the
   floor inside it feeds **rag's** version-skew handshake. A floor written there
   by core would therefore not be an advisory core renders - it would be an
   input to rag's own gate, capable of making rag refuse its own invocation on
   core's say-so. That is actuating cross-package control, not observation, and
   it is precisely the coupling this ADR exists to refuse. The write is
   lock-guarded and sibling-preserving, so the hazard is authorship and
   semantics, not file corruption - which is what makes it easy to miss.

1. **One discovery vocabulary, not one generated block.** The rag guidance is
   spread across seventeen builtin documents - nine agents, seven skills, and
   the `vaultspec-discovery` rule - not the eight this ADR first claimed.

   Collapsing them into a single generated block is rejected on reading them:
   the guidance is genuinely role-specific. An executor's locate step, a
   curator's index-hygiene precondition, and a writer's feasibility audit are
   different instructions that happen to share two facts. Replacing them
   wholesale would destroy real content, and making each document's prose a
   build artifact would also bet on rules reaching subagent context, which is
   provider-dependent.

   What is shared is extracted instead: the fallback sentence and the canonical
   invocation spellings live in one core module, and a test holds every
   entry-point builtin against them. The fallback had five wordings, two of
   which named only `rg`/`fd` and so described a degraded path narrower than
   the one core ships - a substantive error, not a stylistic one. Nested skill
   references are exempt: they are read in the context of a `SKILL.md` that
   already carries the sentence.

   The same suite asserts no builtin spells an MCP-only capability (`intent`,
   relevance feedback, the domain filters) as a CLI flag, and that every rag
   flag named in builtin prose actually exists. Neither error is detectable by
   a reader without going and reading rag's argument parser.

1. **Text filter on `find`.** `find` gains a substring filter over title and
   feature, composing with the existing `feature` / `type` / `date` filters and
   the same `limit` and body tiering. This is the degraded path made real, and
   it is useful independently of rag. It is also what makes the canonical
   fallback sentence true: core's discovery verbs, not just grep.

1. **Tests.** The probe is covered for every state - no entry, entry without
   distribution, present-and-current, present-and-below-floor - entirely from
   fixtures, with no live rag process and no network. A conformance test asserts
   core's MCP tool list is invariant under rag's presence. A third asserts core
   never writes a `minimum_version` onto a distribution entry it does not own,
   so step 3's trap cannot be reintroduced by a later well-meaning change.

## Rationale

The decision follows from the dependency direction. rag depends on core;
therefore core can describe rag but cannot pin it, and any surface core builds
on rag's schema is a surface core cannot keep correct. Every proxying option
fails on that one fact, and the empirical evidence is already in the tree: the
single version constraint core holds about rag went stale by a minor release
without anything noticing, because nothing consumes it.

A capability probe inverts the problem. Presence, declared mode, and version are
not rag's API - they are facts about core's own workspace and the local
environment, which core is already entitled to read. That is why the probe adds
no coupling: there is no rag contract on the path to break. It is also the piece
neither side has today. rag knows its own state but not that an agent is about
to fall back; core writes the fallback but knows nothing. Putting the branch on
data rather than on a prose clause is the whole improvement.

Declining to probe liveness is a deliberate trade, not an oversight. Reachability
would be the single most useful field and the single most expensive one: it means
a socket to a discovered loopback port, a timeout policy, a partial-outcome
state, and a standing bet on rag's status schema. It would convert a total local
function into a networked one and reintroduce every property the constraints
exist to exclude. rag already answers that question authoritatively; core's job
is to name the authority, not to duplicate it badly.

Holding the tool list invariant is what keeps core's contract honest. A tool
that is registered but environmentally wrong is worse than a tool that is
absent, because a host cannot tell the difference until it fails mid-task.

The security constraints are not incidental to that choice - they are most of
why the proxy options lose. Core is trusted by the host as a local, root-bound,
user-authored-content-only surface. Forwarding `project_root`, inheriting an
unbounded path read, and rendering indexed third-party text into agent context
each erode a different part of that trust, and the loopback-port trust boundary
means the text is not even reliably rag's. Keeping search on rag's own channel
leaves those risks with the product that chose them, lets the host attribute
results correctly, and - because core never opens that socket - keeps the
port-trust question entirely outside core's blast radius.

## Consequences

- Core gains a first-class, testable answer to "is semantic search provisioned
  here, and is it current", where today it has an untested English sentence in
  eight files.

- Agents branch on observed state instead of guessing, and the fallback stops
  being "use grep" once `find` has a text filter.

- Core still exposes no semantic search. A user who wants rag's advanced grammar
  runs rag's MCP server alongside core's, which is already how the builtin
  provisioning works.

- **Core takes on no new coupling at all.** The probe reads core's own
  `.mcp.json` and distribution metadata; the only rag artifact it interprets is
  a version string. There is no rag import, no rag API call, no socket, and
  therefore no schema, transport, or availability drift surface. The probe
  cannot be broken by a rag release.

- The cost of that purity is honest and stated: core reports provisioning, not
  health. A rag that is installed, current, and dead reports as present. The
  rendered output must say so plainly and name `vaultspec-rag server doctor` as
  the authority, or the field becomes a false reassurance - which is the one
  failure mode this design can still produce.

- The declared floor needs deliberate maintenance. It is a single constant with
  a test asserting it is the only rag version literal in the tree, which is the
  cheapest honest version of a duty that currently exists nowhere.

- rag's CLI-versus-MCP capability asymmetry is documented here but not fixed;
  closing it is rag's decision to make, and this ADR should be cited when it is.

- Implementing step 5 surfaced an unrelated defect in core's MCP error
  surface, found because the pre-existing `find` test failure was its symptom.
  Every deliberate refusal in `mcp_server/tools/` raised a bare `ValueError`,
  and the MCP SDK wraps anything other than `ToolError` in
  `UnexpectedToolError("Error executing tool <name>")`, discarding the
  message - by design, so a crash leaks nothing to a client. Seventeen
  refusals across `find`, `create`, `edit`, `plan_progress`, `plan_edit`,
  `status`, and the gateway were therefore silently stripped of their
  remediation text, and eight tests were failing on it.

  The gateway cases matter most: the flag-smuggling and denylist guards still
  refused correctly, but a caller could not learn *why*, so an agent's only
  recourse was to retry blindly. Converting those raises to `ToolError`
  restores every message. It is recorded here rather than in a separate ADR
  because it is the reason this feature's own refusals - the `body='full'` row
  ceiling, and the new text filter's composition rules - reach a caller at all.

  Issue #330 carried the three questions that conversion deliberately left
  open; all three are now closed. The catalog parse failure
  (`mcp_server/catalog.py`) is reachable from `discover` and `invoke`, and
  every call fails identically until the install is repaired, so blind retry
  never recovers - it is now narrowed to a `CatalogParseError` (a `ValueError`
  subclass, so callers outside the server are unaffected) and translated to a
  `ToolError` carrying remediation at the gateway boundary, the idiom `plan.py`
  and `orientation.py` already used. `catalog.py` stays decoupled from the SDK,
  and an unexpected `ValueError` from the Typer introspection inside
  `build_catalog` still reads as a crash with its message suppressed. A static
  conformance test now forbids `raise ValueError` anywhere in
  `mcp_server/tools/`, drawn one level wider than the bug because whether a
  given raise escapes to the SDK is not statically decidable; the escape hatch
  is to raise in a lower layer and translate at the boundary. The wider worry -
  that the rushed `mcp` 1.28 -> 2.0 migration hid other unreconciled behaviour
  changes - was audited and found clean: core registers tools only (no
  resources, so the parallel `ResourceError` path is unreachable), and the
  suite runs green with `MCPDeprecationWarning` promoted to an error, so none
  of the capabilities the SDK deprecated on 2026-07-28 - logging,
  client-to-server progress, roots - is touched.
