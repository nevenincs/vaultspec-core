"""Dev-only transcript analytics for empirical CLI usage grounding.

This package normalizes the two agent-CLI transcript corpora (Claude Code
project JSONL and Codex rollout sessions) into a single comparable
:class:`~dev.statistics.normalize.models.CallRecord` stream and computes the metric
families that ground the MCP-server overhaul in real usage rather than
intuition.

The package is a one-purpose development instrument, never a shipped product
surface. The hatchling wheel packages ``src/vaultspec_core`` exclusively, so
this repo-root package sits outside it by construction and is structurally
unshippable.

Subpackages:

- :mod:`dev.statistics.parsers` - source adapters over the raw transcript schemas.
- :mod:`dev.statistics.normalize` - command tokenization and record construction.
- :mod:`dev.statistics.metrics` - the metric families as pure functions.
- :mod:`dev.statistics.report` - the ``records.jsonl`` and ``report.md`` renderers.
"""

from __future__ import annotations
