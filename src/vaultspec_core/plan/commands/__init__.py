"""Command handlers backing the ``vault plan`` CLI verbs.

Each handler is a pure function that takes a parsed :class:`Plan` and
returns a mutated :class:`Plan` plus the canonical identifier of any
newly-created container or row. Callers serialise the result via
:func:`vaultspec_core.plan.serialiser.serialise_plan`.

Modules:

- ``step_ops``: ``add``, ``insert``, ``move``, ``remove``, ``check``,
  ``uncheck``, ``toggle``, ``edit``.
- ``phase_ops``: ``add``, ``insert``, ``move``, ``remove``, ``edit``.
- ``wave_ops``: ``add``, ``insert``, ``move``, ``remove``, ``edit``.
- ``epic_ops``: ``intent`` show / edit.
- ``tier_ops``: ``show``, ``promote``, ``demote``.
"""

from __future__ import annotations
