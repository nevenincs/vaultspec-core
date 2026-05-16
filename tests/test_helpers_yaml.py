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
import threading
import time
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

    def test_import_survives_missing_add_representer(self) -> None:
        """Simulate the issue #85 scenario: ``yaml.add_representer`` is gone.

        Reloading the helpers module under that condition must succeed; only
        the *first* attempt to call ``_yaml_dump`` should raise, and it must
        raise a clear ``AttributeError`` rather than crash at import.
        """
        script = textwrap.dedent(
            """
            import importlib
            import yaml

            import vaultspec_core.core.helpers as helpers_module

            del yaml.add_representer

            helpers = importlib.reload(helpers_module)
            assert helpers._literal_representer_registered is False

            try:
                helpers._yaml_dump({"k": "multi\\nline"})
            except AttributeError:
                print("ok")
            else:
                raise AssertionError("_yaml_dump did not surface AttributeError")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"helpers import/dump contract failed on degraded yaml:\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert result.stdout.strip().endswith("ok")

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


class TestConcurrentRegistration:
    """Two threads first-calling _yaml_dump must not race the registration.

    ``yaml.add_representer`` mutates a class-level dict on PyYAML's
    Dumper.  In CPython that single statement is GIL-serialised, but the
    fix uses a real lock so the contract is "register exactly once" on
    every runtime (non-CPython, free-threaded builds, instrumented
    interpreters).  Surfaced by Gemini-Code-Assist on PR #86.
    """

    def test_double_checked_lock_runs_critical_section_once(self) -> None:
        helpers = _reload_helpers()

        # Replace yaml.add_representer with a counting wrapper so we can
        # observe how many threads actually entered the critical section.
        calls: list[float] = []
        real_add = helpers.yaml.add_representer

        def counting_add(cls, fn):  # type: ignore[no-untyped-def]
            # Sleep briefly so that, without a lock, a second thread that
            # has already cleared the fast-path check has a real chance
            # to enter the critical section before the first thread
            # flips the flag.
            calls.append(time.perf_counter())
            time.sleep(0.05)
            return real_add(cls, fn)

        helpers.yaml.add_representer = counting_add
        try:
            barrier = threading.Barrier(8)
            errors: list[BaseException] = []

            def worker() -> None:
                try:
                    barrier.wait(timeout=5)
                    helpers._yaml_dump({"k": "multi\nline"})
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
        finally:
            helpers.yaml.add_representer = real_add

        assert not errors, f"thread workers raised: {errors!r}"
        assert helpers._literal_representer_registered is True
        assert len(calls) == 1, (
            f"yaml.add_representer was entered {len(calls)} times under "
            "concurrent first-use; the lock must serialize the critical "
            "section to exactly one entry."
        )

    def test_concurrent_first_dump_produces_block_scalar(self) -> None:
        helpers = _reload_helpers()

        barrier = threading.Barrier(8)
        results: list[str] = []
        errors: list[BaseException] = []

        def worker() -> None:
            try:
                barrier.wait(timeout=5)
                results.append(helpers._yaml_dump({"body": "a\nb"}))
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert len(results) == 8
        for out in results:
            assert "body: |" in out, (
                f"thread produced output without block scalar: {out!r}"
            )


@pytest.fixture(autouse=True)
def _restore_helpers_module():
    """Restore a clean helpers module after each test.

    Tests reload the module to exercise the registration flag from a known
    state.  Reload again at teardown so the subsequent test (and the rest
    of the suite) sees the canonical instance with a fresh, lazy flag.
    """
    yield
    _reload_helpers()
