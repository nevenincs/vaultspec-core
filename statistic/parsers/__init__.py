"""Source adapters that read raw transcript schemas into ``CallRecord`` streams.

Each adapter implements the
:class:`~statistic.parsers.base.TranscriptSource` protocol and owns its own
schema quirks entirely - call linkage, exit-status derivation, and cost
attribution - so downstream layers see only normalized records.
"""

from __future__ import annotations
