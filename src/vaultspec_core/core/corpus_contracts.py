"""Registry of corpus facts that tests hold builtin prose against.

Each constant answers one question ``tests/cli/test_corpus_contracts.py``
asks of the bundled builtins. None is a count; each carries the reason it
exists so a failure message can say why. The discovery-sequence registry is
the sibling :mod:`vaultspec_core.core.discovery_guidance`; the template
placeholder registry lives beside the hydrator in
:mod:`vaultspec_core.vaultcore.hydration` and is re-exported here.
"""

from __future__ import annotations

from vaultspec_core.vaultcore.hydration import (
    AUTHOR_FILLED_PLACEHOLDERS,
    MACHINE_FILLED_PLACEHOLDERS,
)

__all__ = [
    "ALWAYS_ON_WORD_BUDGET",
    "AUTHOR_FILLED_PLACEHOLDERS",
    "EXTERNAL_VAULTSPEC_NAMES",
    "FORBIDDEN_VOCABULARY",
    "MACHINE_FILLED_PLACEHOLDERS",
    "RUNTIME_VAULTSPEC_PATHS",
    "SYNTHESIZED_RULES",
]

#: ``vaultspec-*`` names that are products or hosts, not files in the corpus.
EXTERNAL_VAULTSPEC_NAMES = frozenset(
    {
        "vaultspec-core",  # this package's CLI entry point
        "vaultspec-rag",  # companion semantic-search package
        "vaultspec-mcp",  # the MCP server's advertised name (mcp_server/app.py)
        "vaultspec-managed",  # adjective in cli.md for the pre-commit hook
    }
)

#: Rule names that exist only after sync, not as files under builtins/rules.
SYNTHESIZED_RULES = frozenset({"vaultspec-system"})  # core/system.py

#: ``.vaultspec/<rel>`` paths the corpus may name that seeding does not create.
RUNTIME_VAULTSPEC_PATHS = frozenset(
    {
        "workspace.json",  # written by install; per-project state
    }
)

#: Always-on word budget. Sum of the shared system parts (the synthesized
#: ``vaultspec-system`` rule) plus every ``rules/*.builtin.md``. The harness
#: audit measured 4,650 words before the long-horizon rewrite and 2,937
#: after; 3,200 leaves room for a paragraph, not a section. Raise it in a
#: commit that says why.
ALWAYS_ON_WORD_BUDGET = 3200

#: Forbidden vocabulary, each entry with the reason it is forbidden. The
#: reason is the test's failure message.
FORBIDDEN_VOCABULARY: dict[str, str] = {
    "\u2014": "em dash; prose-style-rules.md says spaced hyphen",
    "significant work": "undefined gate word; the horizon vocabulary replaced it",
    "Announce at start": "hosts show skill invocation; the line was removed",
    "I'm using the": "same as 'Announce at start'",
    "EXACTLY TWO": "templates allow tags beyond the required pair",
    '"[[': "related links are single-quoted in every template",
    'tags: ["#': "tags are a YAML block list in every template, not a flow list",
}
