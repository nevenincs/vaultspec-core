"""First-class MCP tool handlers, grouped by domain.

Each module registers a slice of the nine-tool surface onto a shared
``FastMCP`` instance.  :mod:`documents` owns the document-domain mutation
tools (``create`` and ``edit``); further modules add the orientation, plan,
and gateway tools in later phases.  All handlers route every mutation
through the shared ``vaultcore`` / ``plan`` cores and author no creation,
edit, or plan-structure logic here.
"""

from __future__ import annotations

__all__ = ["register_document_tools"]

from .documents import register_document_tools
