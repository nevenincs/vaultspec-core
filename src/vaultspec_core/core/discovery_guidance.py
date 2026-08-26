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

Two properties matter and are enforced by that test:

* The fallback sentence is identical everywhere, so a reader who has seen it
  once does not have to re-read a variant to check whether it says something
  new.
* No builtin invents a rag CLI flag. Several of rag's strongest capabilities -
  intent ranking, relevance feedback, and the noise-domain filters - exist only
  on its MCP tools and as inline query tokens, with no CLI flag at all. Prose
  that spells them as flags would be confidently wrong, and that is a failure a
  reader cannot detect without going and reading rag's argument parser.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

#: The single sentence every builtin uses for rag's absence.
#:
#: Names core's own discovery verbs rather than only ``rg``/``fd``, because the
#: degraded path is not merely grep: ``status``, ``find``, and the vault list
#: and graph verbs carry the orientation half of the sequence, and only the
#: confirmation step is grep's.
DISCOVERY_FALLBACK = (
    "Where `vaultspec-rag` is not installed, the `vaultspec-core` discovery "
    "verbs and grep carry the same sequence."
)

#: Canonical spelling for locating code by meaning.
SEARCH_CODE = '`vaultspec-rag search "<concept and domain nouns>" --type code`'

#: Canonical spelling for locating governing decisions.
#:
#: The directed ``--doc-type adr`` filter, not catch-all ``--type vault``,
#: which is materially noisier for decision recall.
SEARCH_ADR = '`vaultspec-rag search "<intent>" --type vault --doc-type adr`'

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
