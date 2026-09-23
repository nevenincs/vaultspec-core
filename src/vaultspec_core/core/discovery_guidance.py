"""Canonical vocabulary for semantic-search guidance in builtin content.

One home for the sentences and invocation spellings that builtin agents,
skills, and rules use when they tell a model how to discover code and
decisions. Before this module the same two facts - how to invoke rag's search,
and what to do when rag is absent - were restated in seventeen builtin files in
five different wordings, two of which named only ``rg``/``fd`` and so described
a degraded path narrower than the one core actually provides.

Nothing here is generated into the builtin files at build time; they are
authored content and stay readable as authored content. These constants are the
single source of truth that
``src/vaultspec_core/tests/test_discovery_guidance.py`` holds every builtin
against, which is what stops the wordings diverging again without also freezing
each document's role-specific framing.

Three properties matter and are enforced by that test:

* The fallback sentence is identical everywhere, so a reader who has seen it
  once does not have to re-read a variant to check whether it says something
  new.
* No builtin offers rag's vault search. Decision and vault-fact questions go
  to core's ``search``, whose reply names the search to run when it declines
  or fails, resolved from what the workspace provisions; guidance that chose a
  route itself would need runtime state it cannot see.
* No builtin invents a rag CLI flag. Several of rag's strongest capabilities -
  intent ranking, relevance feedback, and the noise-domain filters - exist only
  on its MCP tools and as inline query tokens, with no CLI flag at all. Prose
  that spells them as flags would be confidently wrong, and that is a failure a
  reader cannot detect without going and reading rag's argument parser.
"""

from __future__ import annotations

#: The single sentence every builtin uses for rag's absence.
#:
#: Names core's own discovery verbs rather than only ``rg``/``fd``, because the
#: degraded path is not merely grep: ``status``, ``find``, and the vault list
#: and graph verbs carry the orientation half of the sequence, and only the
#: confirmation step is grep's.
#:
#: Says *unavailable* rather than *not installed* because the degraded path is
#: reached by a rag that is installed but whose service is down just as often
#: as by one that was never installed, and the reader's next move is the same
#: either way.
DISCOVERY_FALLBACK = (
    "Where `vaultspec-rag` is unavailable, the `vaultspec-core` discovery "
    "verbs and grep carry the same sequence."
)

#: Canonical spelling for locating code by meaning.
SEARCH_CODE = '`vaultspec-rag search "<concept and domain nouns>" --type code`'

#: rag's vault search before its record-type filter. ``--doc-type`` narrows it
#: to one type or, comma-separated, a union of types. Only a declined core
#: search names it, over the record types that search was asked for; no
#: builtin offers it.
RAG_VAULT_SEARCH = 'vaultspec-rag search "<intent>" --type vault'

#: Core's listing verb, the orientation half of the no-semantic route; an
#: optional record type narrows it. Its MCP counterpart is ``find``.
LIST_VAULT = "vaultspec-core vault list"

#: Canonical spelling for asking the vault a question through core's hosted
#: search, which answers with the passage and its line range and abstains when
#: nothing answers.
SEARCH_VAULT = '`vaultspec-core vault search "<question>"`'

#: The single sentence routing decision and vault-fact questions.
#:
#: State-free: it carries no runtime condition, because the reader who needs
#: it - a dispatched worker, a read-only session - often cannot see the state
#: a condition would name, and a configured key can still be rejected. The
#: search itself decides: when it declines or fails, its reply names the next
#: step, a rag vault search when rag is provisioned and core's listing verbs
#: and grep otherwise. Code search is rag's alone and is not routed.
VAULT_SEARCH_ROUTING = (
    f"Search decisions and vault facts with {SEARCH_VAULT} (MCP: `search`); "
    "when it declines or fails, run the next step its reply names."
)

#: rag CLI flags that exist, as of the floor in
#: :data:`~vaultspec_core.core.diagnosis.collectors_companion.RAG_MINIMUM_VERSION`.
#:
#: Guidance may name any of these. Anything else spelled as a flag is either a
#: typo or an MCP-only capability being mis-described.
RAG_SEARCH_FLAGS = frozenset(
    {
        "--allow-fallback",
        "--class-name",
        "--date",
        "--doc-type",
        "--exclude-path",
        "--extractor-id",
        "--extractor-version",
        "--feature",
        "--function-name",
        "--include-path",
        "--language",
        "--limit",
        "--locator-kind",
        "--max-results",
        "--path",
        "--prefer",
        "--scores",
        "--source-path",
        "--structure",
        "--tag",
        "--timeout",
        "--type",
        "--verbose",
    }
)

#: Capabilities reachable only through rag's MCP tools or inline query tokens.
#:
#: Each is a real rag capability with no CLI flag. Guidance that wants one must
#: point at rag's MCP tools; spelling it as a flag would be wrong.
MCP_ONLY_CAPABILITIES = frozenset(
    {
        "--intent",
        "--like",
        "--unlike",
        "--like-id",
        "--unlike-id",
        "--exclude-domain",
        "--only-domain",
        "--include-domain",
    }
)

#: Rule name the rest of the corpus cites. The file is the single home of the
#: locate / read-whole / confirm sequence.
DISCOVERY_RULE = "vaultspec-discovery"

#: Path of that home, relative to the builtins root.
DISCOVERY_HOME = "rules/vaultspec-discovery.builtin.md"

#: Sentences the home must define. A sentence missing from the home is a
#: broken registry, not a missing citation.
DISCOVERY_CANONICAL_SENTENCES = (
    DISCOVERY_FALLBACK,
    SEARCH_CODE,
    SEARCH_VAULT,
    VAULT_SEARCH_ROUTING,
)

#: Entry points allowed to spell ``vaultspec-rag`` out instead of citing the
#: rule. Each is a role whose job is search itself; a reader arriving there
#: needs the invocation, not a pointer. Everything else cites
#: :data:`DISCOVERY_RULE` by name. Paths are relative to the builtins root.
DISCOVERY_RESTATERS = frozenset(
    {
        # Auditing a codebase into a Reference: search is the deliverable.
        "agents/vaultspec-reference-auditor.md",
        # Reconciles ADRs against code: decision recall is the whole task.
        "agents/vaultspec-docs-curator.md",
        # The skill that exists to locate code for the pipeline.
        "skills/vaultspec-code-research/SKILL.md",
        # Curator's skill; same reason as the persona.
        "skills/vaultspec-curate/SKILL.md",
    }
)

#: Vocabulary that marks a restatement of the sequence rather than a citation.
#: A file using it without citing the rule and without being a registered
#: restater has grown a second definition.
DISCOVERY_SEQUENCE_MARKER = "epicenter"
