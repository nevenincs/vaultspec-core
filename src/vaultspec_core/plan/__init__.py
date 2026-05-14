"""Plan-document parser, model, and operations for ``vaultspec-core vault plan``.

Implements the natural-language convention defined in
``.vault/adr/2026-05-05-plan-hardening-adr.md`` (Wave 1) and the CLI
surface defined in ``.vault/adr/2026-05-06-plan-hardening-adr.md``
(Wave 2). The package is consumed by :mod:`vaultspec_core.cli.vault_cmd`
to back the ``vaultspec-core vault plan`` command group.

Public surface (re-exported here as it lands across Wave 2 Phases):

- ``frontmatter`` (W02.P01.S36): plan-frontmatter parsing for ``tier``,
  ``related``, ``tags``, ``date``.
- ``parser`` (W02.P01.S37): hierarchy parsing for Wave / Phase / Step
  blocks against the convention's row contract.
- ``identifiers`` (W02.P01.S38): canonical ``S##``/``P##``/``W##``
  extraction and the per-document next-available counter.
- ``display_path`` (W02.P01.S39): tier-conditional display-path
  computation from the current ancestor chain.
- ``serialiser`` (W02.P01.S40): in-memory model -> markdown emission
  preserving document order.
- ``commands`` (W02.P02 onward): CLI command handlers.
- ``checks`` (W02.P02): detection rules for ``vaultspec-core vault plan check``.
- ``fixes`` (W02.P02): idempotent autofix transformations for
  ``vaultspec-core vault plan check --fix``.
"""

from __future__ import annotations
