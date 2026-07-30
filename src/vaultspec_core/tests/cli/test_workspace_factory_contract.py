"""The workspace factory canonicalizes the root it is handed.

Scaffolding derives every provider path with :meth:`pathlib.Path.relative_to`,
which compares lexically rather than by identity: a path can be genuinely
inside another and still raise, if the two spell the same directory
differently. That is not hypothetical here. On a Windows CI runner
``tempfile`` hands back an 8.3 short path (``C:\\Users\\RUNNER~1\\...``) while
the entries walked underneath it come back expanded
(``C:\\Users\\runneradmin\\...``), so a factory built on an unresolved root
failed every provider scaffold with "is not in the subpath of" - and only on
that runner, which is why it survived local runs.

The real entry points never had the problem, because ``--target`` is put
through :func:`~vaultspec_core.cli._target.resolve_effective_target`, which
resolves. The factory stands in for the CLI, so it owes callers the same
guarantee. These pin it directly rather than through a scaffold run, so the
contract survives independently of whichever provider layout happens to
exercise it.

Every assertion reads real on-disk state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def test_traversal_in_the_root_is_canonicalized(tmp_path: Path) -> None:
    """A root spelled with ``..`` resolves to the directory it denotes.

    Also pins absoluteness, which is what gives later ``relative_to`` calls a
    common base to compare against.
    """
    nested = tmp_path / "workspace" / "inner"
    nested.mkdir(parents=True)

    factory = WorkspaceFactory(nested / ".." / "inner")

    assert factory.root == nested.resolve()
    assert ".." not in factory.root.parts
    assert factory.root.is_absolute()


def test_resolved_root_is_a_valid_relative_to_base_for_its_own_children(
    tmp_path: Path,
) -> None:
    """The canonical root is a usable base for the paths scaffolding derives.

    This is the property the provider scaffolder actually depends on: a child
    discovered by walking the tree must be expressible relative to the stored
    root. Walking yields resolved paths, so an unresolved root breaks it.
    """
    root = tmp_path / "workspace"
    (root / ".claude" / "rules").mkdir(parents=True)

    factory = WorkspaceFactory(root)
    discovered = sorted(factory.root.rglob("rules"))

    assert discovered, "expected the walk to find the scaffolded directory"
    for child in discovered:
        assert child.resolve().relative_to(factory.root)
