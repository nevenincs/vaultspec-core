"""Build each distinct test workspace once, then clone it per test.

Several packages need "a real, fully installed workspace" per test, and each
used to build one from scratch. Every one of those trees was identical at the
moment the fixture yielded - the corpus generator is seeded and the install is
a pure function of the bundled builtins - so the construction is what repeats,
not the result.

The cache lives here rather than in the root ``conftest.py`` for one reason:
three packages' conftests name this type in their fixture signatures, and a
type that only pytest's rootdir import can reach is not importable by name from
inside the package. The session fixture that hands one out stays in the root
conftest, which is where a fixture has to be to reach every lane.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["WorkspaceTemplates"]


class WorkspaceTemplates:
    """Builds each distinct workspace once, then clones it per test."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._templates: dict[str, Path] = {}

    def clone(self, key: str, dest: Path, build: Callable[[Path], None]) -> Path:
        """Return *dest*, populated as a copy of the template named *key*.

        Args:
            key: Identifies the tree. Two callers passing the same key must
                want byte-identical trees, because the second one gets a copy
                of whatever the first one built.
            dest: Directory to create. Must not already exist.
            build: Populates a fresh directory. Called at most once per key
                per session.

        Returns:
            *dest*, now holding a private copy of the template.
        """
        from vaultspec_core.tests.cli.workspace_factory import rebase_workspace_paths

        template = self._templates.get(key)
        if template is None:
            template = self._root / key
            build(template)
            self._templates[key] = template
        # `dirs_exist_ok` stays False: a caller handing us an existing
        # directory has confused this with a merge, and silently blending two
        # workspaces would be a very hard failure to read.
        shutil.copytree(template, dest, symlinks=True)
        # An installed workspace records where it lives, so a raw copy would
        # claim the template's files as its own.
        rebase_workspace_paths(template, dest)
        return dest
