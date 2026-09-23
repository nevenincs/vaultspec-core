"""Every environment variable the codebase touches is declared once, and documented.

Two registries declare the environment, one per side of the shipping boundary:
``vaultspec_core.config.CONFIG_REGISTRY`` for the product - its ``VAULTSPEC_*``
settings, the external conventions it honours, the internal marker it sets for
its own children - and ``dev.environment.HARNESS_REGISTRY`` for the development
harness, which must not import the product. ``.env.example`` is where a reader
finds both. The ways they can come apart, one check each:

- a name in ``.env.example`` neither registry declares documents a variable
  nothing reads (**extra**);
- a declared name absent from ``.env.example`` is a variable nobody can
  discover (**missing**);
- a variable both registries declare must be documented by the product alone,
  and a harness entry claiming that must really be a product entry;
- a module touching ``os.environ``, ``os.getenv`` or ``os.putenv`` outside its
  side's registry module reads or sets a variable neither registry sees;
- a ``VAULTSPEC_*`` string literal no registry declares is a new variable being
  invented beside the registries, whatever reads it.

On the product side, test source is out of scope for the last two: a test
builds environments for the code it exercises, and names undeclared variables
on purpose to prove they are ignored. Under ``dev/`` nothing is exempt.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from dev.environment import HARNESS_REGISTRY
from vaultspec_core.config import CONFIG_REGISTRY

pytestmark = [pytest.mark.repo, pytest.mark.precommit]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The shipped package whose source is scanned.
PACKAGE_ROOT = PROJECT_ROOT / "src" / "vaultspec_core"

#: The one product package allowed to touch the process environment.
CONFIG_ROOT = PACKAGE_ROOT / "config"

#: The development harness.
DEV_ROOT = PROJECT_ROOT / "dev"

#: The one harness module allowed to touch the process environment.
DEV_ENVIRONMENT = DEV_ROOT / "environment.py"

#: The catalogue of both registries.
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

#: ``os`` members that read or change the process environment.
_ENVIRONMENT_MEMBERS = frozenset(
    {"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"}
)

#: Modules that expose those members: ``os`` and the platform modules behind it.
_ENVIRONMENT_MODULES = frozenset({"os", "posix", "nt"})

#: A product variable name as a whole word. The boundaries keep an identifier
#: such as ``EXTERNAL_VAULTSPEC_NAMES`` from reading as one.
_PRODUCT_NAME = re.compile(r"\bVAULTSPEC_[A-Z0-9_]+\b")

#: One assignment in ``.env.example``, commented out or live.
_EXAMPLE_ASSIGNMENT = re.compile(
    r"^#?\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)=", re.MULTILINE
)

#: ``VAULTSPEC_*`` literals that are not environment variables, each with the
#: reason. Keep this to names that could never be one.
_NOT_VARIABLES = {
    "VAULTSPEC_INSTALL_MODE_COMMAND": (
        "the @@...@@ launch-command placeholder core writes into an MCP "
        "manifest and substitutes itself"
    ),
    "VAULTSPEC_INSTALL_MODE_ARGS": (
        "the @@...@@ launch-arguments placeholder core writes into an MCP "
        "manifest and substitutes itself"
    ),
}


def _registry_names() -> set[str]:
    """Return every name the product registry declares."""
    names = {var.env_name for var in CONFIG_REGISTRY}
    assert names, "CONFIG_REGISTRY declares nothing"
    return names


def _harness_names() -> set[str]:
    """Return every name the harness registry declares."""
    names = {var.name for var in HARNESS_REGISTRY}
    assert names, "HARNESS_REGISTRY declares nothing"
    return names


def _example_names() -> set[str]:
    """Return every name ``.env.example`` assigns, commented out or not."""
    assert ENV_EXAMPLE.is_file(), f"missing {ENV_EXAMPLE}"
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    names = {match["name"] for match in _EXAMPLE_ASSIGNMENT.finditer(text)}
    assert names, f"no NAME= assignments found in {ENV_EXAMPLE}"
    return names


def _is_test_source(path: Path) -> bool:
    relative = path.relative_to(PACKAGE_ROOT)
    return (
        "tests" in relative.parts[:-1]
        or relative.name.startswith("test_")
        or relative.name == "conftest.py"
    )


def _python_files(root: Path) -> list[Path]:
    """Return every Python file under *root*."""
    found = sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )
    assert found, f"no Python files found under {root}"
    return found


def _sources(root: Path) -> list[Path]:
    """Return the non-test product sources under *root*."""
    found = [path for path in _python_files(root) if not _is_test_source(path)]
    assert found, f"no non-test Python sources found under {root}"
    return found


def _outside_config() -> list[Path]:
    """Return the package's non-test sources outside the config package."""
    found = [path for path in _sources(PACKAGE_ROOT) if CONFIG_ROOT not in path.parents]
    assert found, f"no sources found outside {CONFIG_ROOT}"
    return found


def _dev_outside_environment() -> list[Path]:
    """Return every harness file except the harness's environment module."""
    found = [path for path in _python_files(DEV_ROOT) if path != DEV_ENVIRONMENT]
    assert found, f"no Python files found under {DEV_ROOT}"
    return found


def _environment_access(path: Path) -> list[str]:
    """Return each place *path* reaches the process environment."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases: set[str] = set()
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in _ENVIRONMENT_MODULES
            )
        elif isinstance(node, ast.ImportFrom) and node.module in _ENVIRONMENT_MODULES:
            found.extend(
                f"{node.lineno}: from {node.module} import {alias.name}"
                for alias in node.names
                if alias.name in _ENVIRONMENT_MEMBERS
            )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _ENVIRONMENT_MEMBERS
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            found.append(f"{node.lineno}: {node.value.id}.{node.attr}")
    return found


def _product_name_literals(path: Path) -> list[tuple[int, str]]:
    """Return each ``VAULTSPEC_*`` name inside a string literal in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        (node.lineno, match.group())
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for match in _PRODUCT_NAME.finditer(node.value)
    ]


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestEnvExampleMatchesTheRegistries:
    def test_no_extra_variable_is_documented(self) -> None:
        declared = _registry_names() | _harness_names()
        extra = sorted(_example_names() - declared)

        assert not extra, (
            ".env.example documents variables neither CONFIG_REGISTRY nor "
            "HARNESS_REGISTRY declares. Declare them, or remove them from "
            f".env.example: {extra}"
        )

    def test_no_declared_variable_is_missing(self) -> None:
        declared = _registry_names() | _harness_names()
        missing = sorted(declared - _example_names())

        assert not missing, (
            "These declared variables are not documented in .env.example. Add "
            "each with a description, its type and its default, in the file's "
            f"format and in its side's section: {missing}"
        )

    def test_a_variable_both_sides_read_is_documented_by_the_product(self) -> None:
        product = _registry_names()
        claimed = {var.name for var in HARNESS_REGISTRY if var.description is None}
        described = {var.name for var in HARNESS_REGISTRY if var.description}

        assert claimed <= product, (
            "harness entries defer their description to the product registry, "
            f"which does not declare them: {sorted(claimed - product)}"
        )
        assert not described & product, (
            "these harness entries restate a variable the product registry "
            "already describes; declare them with description=None: "
            f"{sorted(described & product)}"
        )


class TestOnlyTheRegistryModulesTouchTheEnvironment:
    def test_the_detector_sees_the_config_packages_own_access(self) -> None:
        # The config package is the sanctioned reader; finding its reads is
        # what shows the detector below is not blind.
        seen = [
            hit for path in _sources(CONFIG_ROOT) for hit in _environment_access(path)
        ]

        assert seen, f"no environment access detected under {CONFIG_ROOT}"

    def test_the_detector_sees_the_harness_modules_own_access(self) -> None:
        assert DEV_ENVIRONMENT.is_file(), f"missing {DEV_ENVIRONMENT}"

        assert _environment_access(DEV_ENVIRONMENT), (
            f"no environment access detected in {DEV_ENVIRONMENT}"
        )

    def test_no_module_outside_config_touches_the_environment(self) -> None:
        offenders = [
            f"{_rel(path)}:{hit}"
            for path in _outside_config()
            for hit in _environment_access(path)
        ]

        assert not offenders, (
            "Only vaultspec_core.config may touch the process environment. Read "
            "a registered variable with get_config() or env_value(), and build a "
            "child environment with child_environment():\n  " + "\n  ".join(offenders)
        )

    def test_no_harness_module_outside_its_registry_touches_the_environment(
        self,
    ) -> None:
        offenders = [
            f"{_rel(path)}:{hit}"
            for path in _dev_outside_environment()
            for hit in _environment_access(path)
        ]

        assert not offenders, (
            "Only dev/environment.py may touch the process environment under "
            "dev/. Read a declared variable with environment.value(), and "
            "build a child environment with environment.child_environment():\n  "
            + "\n  ".join(offenders)
        )


class TestNoVariableIsInventedBesideTheRegistries:
    def test_the_scan_sees_the_registries_own_names(self) -> None:
        product = {
            name
            for path in _sources(CONFIG_ROOT)
            for _, name in _product_name_literals(path)
        }
        harness = {name for _, name in _product_name_literals(DEV_ENVIRONMENT)}

        assert product & _registry_names(), (
            f"no registered VAULTSPEC_* literal detected under {CONFIG_ROOT}"
        )
        assert harness & _harness_names(), (
            f"no declared VAULTSPEC_* literal detected in {DEV_ENVIRONMENT}"
        )

    def test_the_exemptions_are_still_needed_and_never_registered(self) -> None:
        seen = {
            name
            for path in _outside_config()
            for _, name in _product_name_literals(path)
        }
        declared = _registry_names() | _harness_names()

        assert not set(_NOT_VARIABLES) & declared
        assert set(_NOT_VARIABLES) <= seen, (
            "an exemption no longer matches any literal; remove it: "
            f"{sorted(set(_NOT_VARIABLES) - seen)}"
        )

    def test_every_product_name_literal_is_registered(self) -> None:
        known = _registry_names() | set(_NOT_VARIABLES)
        offenders = [
            f"{_rel(path)}:{line}: {name}"
            for path in _sources(PACKAGE_ROOT)
            for line, name in _product_name_literals(path)
            if name not in known
        ]

        assert not offenders, (
            "These VAULTSPEC_* names are not declared in CONFIG_REGISTRY. "
            "Declare a new variable there, and document it in .env.example:\n  "
            + "\n  ".join(offenders)
        )

    def test_every_harness_name_literal_is_declared(self) -> None:
        known = _registry_names() | _harness_names() | set(_NOT_VARIABLES)
        offenders = [
            f"{_rel(path)}:{line}: {name}"
            for path in _python_files(DEV_ROOT)
            for line, name in _product_name_literals(path)
            if name not in known
        ]

        assert not offenders, (
            "These VAULTSPEC_* names under dev/ are declared by neither "
            "registry. Declare a harness variable in dev/environment.py, and "
            "document it in .env.example:\n  " + "\n  ".join(offenders)
        )
