"""Renderers for the analysis outputs.

This subpackage writes the full normalized ``records.jsonl`` stream and the
aggregate-only ``report.md`` into the gitignored ``statistic/out/`` directory;
neither artifact carries raw command bodies, secrets, or personal paths.
"""

from __future__ import annotations
