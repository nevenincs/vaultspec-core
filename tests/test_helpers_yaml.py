"""Regression tests for the lazy YAML representer in :mod:`vaultspec_core.core.helpers`.

Issue #85: a top-level ``yaml.add_representer(...)`` call at module scope
made the entire framework un-importable when PyYAML's surface was even
partially broken (e.g. a corrupt install missing ``yaml/__init__.py``).
The fix moves the registration into a lazy
:func:`~vaultspec_core.core.helpers._ensure_literal_representer` that runs
on first ``_yaml_dump`` call.

These tests pin that contract:

- importing ``vaultspec_core.core`` does **not** mutate PyYAML's global
  representer registry until a serialization actually happens;
- the lazy registration is idempotent and survives module reload;
- ``_yaml_dump`` (and ``build_file``) still produce literal block scalars
  for multi-line strings, matching the pre-fix output;
- importing the package on a degraded PyYAML (``add_representer`` missing)
  succeeds; only the *first* dump raises.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest
import yaml

import vaultspec_core.core.helpers as helpers_module

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = [pytest.mark.unit]


def _reload_helpers() -> ModuleType:
    """Reload :mod:`vaultspec_core.core.helpers` and return the fresh module."""
    return importlib.reload(helpers_module)


class TestNoImportTimeSideEffect:
    """Importing helpers must not mutate PyYAML's global state."""

    def test_fresh_subprocess_import_leaves_yaml_registry_untouched(self) -> None:
        """A fresh interpreter that imports ``vaultspec_core.core`` must not
        register ``_LiteralStr`` against PyYAML's default Dumper.

        Running in a subprocess guarantees a pristine ``yaml`` module so the
        observation is not contaminated by a prior import in the test
        session.
        """
        script = textwrap.dedent(
            """
            import yaml

            before = dict(yaml.Dumper.yaml_representers)

            import vaultspec_core.core  # triggers helpers import

            after = dict(yaml.Dumper.yaml_representers)

            # The representer registry must be byte-for-byte identical: the
            # lazy fix means importing core/helpers does not touch yaml's
            # global Dumper at all.
            assert before == after, (
                "vaultspec_core.core import mutated yaml.Dumper.yaml_representers"
            )
            print("ok")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert result.stdout.strip().endswith("ok")


class TestLazyRegistrationOnDump:
    """``_yaml_dump`` registers the representer on first call and reuses it."""

    def test_dump_registers_then_marks_flag_true(self) -> None:
        helpers = _reload_helpers()

        assert helpers._literal_representer_registered is False, (
            "module-level reload must leave the lazy flag unset"
        )

        out = helpers._yaml_dump({"key": "single line"})

        assert helpers._literal_representer_registered is True
        assert "key:" in out

    def test_ensure_literal_representer_is_idempotent(self) -> None:
        helpers = _reload_helpers()
        helpers._ensure_literal_representer()
        helpers._ensure_literal_representer()
        helpers._ensure_literal_representer()
        assert helpers._literal_representer_registered is True

    def test_multiline_string_uses_literal_block_scalar(self) -> None:
        helpers = _reload_helpers()

        rendered = helpers._yaml_dump(
            {
                "name": "single",
                "body": "line one\nline two\nline three",
            }
        )

        assert "body: |" in rendered, (
            f"multi-line value did not use '|' block scalar:\n{rendered}"
        )
        assert "line one" in rendered
        assert "line two" in rendered
        # Single-line keys must remain plain.
        assert "name: single" in rendered

    def test_build_file_round_trips_through_yaml_safe_load(self) -> None:
        helpers = _reload_helpers()

        rendered = helpers.build_file(
            {"name": "demo", "instructions": "step one\nstep two"},
            body="hello",
        )

        head, _, body = rendered.partition("\n---\n")
        assert head.startswith("---\n")
        assert body.strip() == "hello"

        front = yaml.safe_load(head[len("---\n") :])
        assert front == {"name": "demo", "instructions": "step one\nstep two"}


class TestDegradedPyYAML:
    """The framework must remain importable on a partially broken PyYAML."""

    def test_import_survives_missing_add_representer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate the issue #85 scenario: ``yaml.add_representer`` is gone.

        Reloading the helpers module under that condition must succeed; only
        the *first* attempt to call ``_yaml_dump`` should raise, and it must
        raise a clear ``AttributeError`` rather than crash at import.
        """
        monkeypatch.delattr(yaml, "add_representer", raising=False)

        helpers = _reload_helpers()
        assert helpers._literal_representer_registered is False

        with pytest.raises(AttributeError):
            helpers._yaml_dump({"k": "multi\nline"})

    def test_core_package_import_survives_missing_add_representer(
        self,
    ) -> None:
        """Importing ``vaultspec_core.core`` must succeed on a degraded yaml.

        Runs in a subprocess so we can mutate the ``yaml`` module before
        the package is imported, exactly mirroring the production failure
        mode where the broken ``yaml`` install is loaded first.
        """
        script = textwrap.dedent(
            """
            import yaml

            del yaml.add_representer

            # The whole point of issue #85: this import must succeed even
            # with yaml.add_representer missing.
            import vaultspec_core.core

            assert hasattr(vaultspec_core.core, "build_file")
            print("ok")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"core import crashed on degraded yaml:\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert result.stdout.strip().endswith("ok")


@pytest.fixture(autouse=True)
def _restore_helpers_module():
    """Restore a clean helpers module after each test.

    Tests reload the module to exercise the registration flag from a known
    state.  Reload again at teardown so the subsequent test (and the rest
    of the suite) sees the canonical instance with a fresh, lazy flag.
    """
    yield
    _reload_helpers()
