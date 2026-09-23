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

* The code-search invocation and the fallback sentence live in the
  discovery rule alone. Other builtins cite the rule, so a reader never has
  to compare a variant against the original.
* No builtin offers rag's vault search. Decision and vault-fact questions go
  to core's ``search``, whose reply names the search to run when it declines
  or fails, resolved from what the workspace provisions; guidance that chose a
  route itself would need runtime state it cannot see. The routing sentence
  lives in the discovery rule alone; other builtins cite the rule.
* No builtin invents a rag CLI flag. Several of rag's strongest capabilities -
  intent ranking, relevance feedback, and the noise-domain filters - exist only
  on its MCP tools and as inline query tokens, with no CLI flag at all. Prose
  that spells them as flags would be confidently wrong, and that is a failure a
  reader cannot detect without going and reading rag's argument parser.
"""

from __future__ import annotations

#: The discovery rule's sentence for rag's absence.
#:
#: rag is the only semantic code search, so its absence changes the locate
#: step for code: a targeted grep takes its place. That is the one case where
#: grep leads, which is why the sentence names it rather than leaving it to
#: contradict "grep is the confirmation step". Vault questions are not covered
#: here; the search reply names their next step.
#:
#: Says *unavailable* rather than *not installed* because a rag whose service
#: is down reaches the same path as one never installed. The report line lets
#: a reviewer weigh findings that were located without semantic search.
DISCOVERY_FALLBACK = (
    "Where `vaultspec-rag` is unavailable, locate code with a targeted grep, "
    "and say in your report that discovery ran without semantic search."
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

#: The decision listing that runs beside search. Summary-based recall can miss
#: a record whose answer lives only in body detail, so listing the ADRs stays
#: mandatory until that recall is measured.
LIST_ADR = f"`{LIST_VAULT} adr`"

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
    LIST_ADR,
    SEARCH_CODE,
    SEARCH_VAULT,
    VAULT_SEARCH_ROUTING,
)

#: Entry points allowed to name ``vaultspec-rag`` outside the home. Each keeps
#: rag's code index current before a reconciliation, a step no other role
#: takes; for the search itself and the fallback it cites :data:`DISCOVERY_RULE`
#: like everything else. No builtin restates the code-search invocation or the
#: fallback: both live in the home alone. Paths are relative to the builtins
#: root.
RAG_INDEX_CHECKERS = frozenset(
    {
        "agents/vaultspec-docs-curator.md",
        "skills/vaultspec-curate/SKILL.md",
    }
)

#: Vocabulary that marks a restatement of the sequence rather than a citation.
#: A file using it without citing the rule has grown a second definition.
DISCOVERY_SEQUENCE_MARKER = "epicenter"
