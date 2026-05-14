"""Command handlers backing the ``vaultspec-core vault plan`` CLI verbs.

Each handler is a pure function that takes a parsed :class:`Plan` and
returns a mutated :class:`Plan` plus the canonical identifier of any
newly-created container or row. Callers serialise the result via
:func:`vaultspec_core.plan.serialiser.serialise_plan`.

Modules:

- ``step_ops``: ``add``, ``insert``, ``move``, ``remove``, ``check``,
  ``uncheck``, ``toggle``, ``edit``.
- ``phase_ops``: ``add``, ``insert``, ``move``, ``remove``, ``renumber``,
  ``edit``.
- ``wave_ops``: ``add``, ``insert``, ``move``, ``remove``, ``edit``.
- ``epic_ops``: ``intent`` show / edit.
- ``tier_ops``: ``show``, ``promote``, ``demote``.

**Lookup complexity.** ``find_step`` / ``find_phase`` / ``find_wave``
and the parent-resolver helpers (``_phase_of`` / ``_wave_of`` /
``_wave_id_of``) are O(n) walks over the plan's flat container lists.
This is acceptable for the interactive CLI surface where each command
invocation performs one or two lookups against a freshly-parsed Plan.
If bulk operations land later (e.g. a single-process scripted
mutation pass), introduce ``canonical_id -> object`` indices on the
:class:`Plan` model and route the lookups through them. There is no
measured hot path today.
"""

from __future__ import annotations
