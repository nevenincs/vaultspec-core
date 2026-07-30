"""Vault document relationship graph backed by ``networkx.DiGraph``.

Scans ``.vault/`` content, resolves wiki-links and ``related:`` frontmatter
fields into directed edges; exposes query, ASCII/Rich render (``phart``), and
JSON-serialisation (node-link format) operations.
Key exports: :class:`VaultGraph` (main entry point, instantiate with vault
root), :class:`DocNode` (per-document node with frontmatter and link
metadata), :class:`GraphCounts` (cheap descriptive counts for render
paths), :class:`GraphMetrics` (opt-in aggregate ``networkx`` statistics).
Consumed by :mod:`vaultspec_core.cli` graph sub-commands.
"""

from .api import DocNode as DocNode
from .api import GraphMetrics as GraphMetrics
from .api import VaultGraph as VaultGraph
from .models import GraphCounts as GraphCounts
