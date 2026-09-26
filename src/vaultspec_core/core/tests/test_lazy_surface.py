"""The package's re-exported surface, resolved lazily but declared twice.

``vaultspec_core.core`` resolves its re-exports through a module
``__getattr__`` backed by a name-to-submodule map. A type checker cannot
read that map, so the same names are also declared in a ``TYPE_CHECKING``
block. Two declarations of one surface drift: a name added to the block
alone is an ``AttributeError`` at runtime, and a name added to the map
alone is an unresolved import to every checker and editor. These tests
hold them together, and hold each entry to the object its submodule
actually defines.

The import-cost promise is checked from a fresh subprocess, because the
interpreter running these tests has already imported the whole package.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import vaultspec_core.core as core_package
from vaultspec_core.core import _EXPORTS

pytestmark = [pytest.mark.unit]

_SOURCE = Path(core_package.__file__)


def _type_checking_declarations() -> dict[str, str]:
    """Return the name-to-submodule pairs the TYPE_CHECKING block declares."""
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    declared: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for statement in ast.walk(node):
            if isinstance(statement, ast.ImportFrom) and statement.module:
                for alias in statement.names:
                    declared[alias.asname or alias.name] = statement.module
    return declared


class TestTheTwoDeclarationsAgree:
    def test_every_mapped_name_is_declared_for_the_type_checker(self) -> None:
        missing = sorted(set(_EXPORTS) - set(_type_checking_declarations()))
        assert not missing, (
            "these names resolve at runtime but no type checker can see them: "
            f"{missing}"
        )

    def test_every_declared_name_is_mapped_for_the_runtime(self) -> None:
        missing = sorted(set(_type_checking_declarations()) - set(_EXPORTS))
        assert not missing, (
            f"these names would raise AttributeError at runtime: {missing}"
        )

    def test_both_name_the_same_submodule(self) -> None:
        declared = _type_checking_declarations()
        disagreements = {
            name: (module, declared[name])
            for name, module in _EXPORTS.items()
            if declared.get(name) != module
        }
        assert not disagreements


class TestEveryExportResolves:
    @pytest.mark.parametrize("name", sorted(_EXPORTS), ids=sorted(_EXPORTS))
    def test_it_is_the_object_its_submodule_defines(self, name: str) -> None:
        from importlib import import_module

        submodule = import_module(f"vaultspec_core.core.{_EXPORTS[name]}")
        assert getattr(core_package, name) is getattr(submodule, name)

    def test_an_unknown_name_still_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            core_package.__getattr__("no_such_export")

    def test_dir_lists_the_surface(self) -> None:
        assert set(_EXPORTS) <= set(dir(core_package))


class TestImportingOneExceptionStaysCheap:
    """The whole point of the laziness, proven where it can be seen.

    Python imports a package before any module inside it, so importing one
    exception class from ``vaultspec_core.core.exceptions`` runs this
    package's ``__init__``. It must not drag the sync engine, the agent
    collector or the YAML parser in behind it.
    """

    def test_the_heavy_submodules_stay_unimported(self) -> None:
        probe = (
            "import sys\n"
            "from vaultspec_core.core.exceptions import ConfigurationError\n"
            "loaded = sorted(\n"
            "    name for name in sys.modules\n"
            "    if name.startswith('vaultspec_core.core.')\n"
            ")\n"
            "print(','.join(loaded))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

        loaded = {name for name in result.stdout.strip().split(",") if name}
        assert loaded == {"vaultspec_core.core.exceptions"}
