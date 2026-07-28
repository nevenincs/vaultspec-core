"""Framework and provider directory structural collectors.

Assesses the presence and coherence of the ``.vaultspec/`` framework tree, the
manifest's agreement with provider directories on disk, and the completeness
of an individual provider's configuration directory. All imports from
``core.*`` modules are deferred inside function bodies to prevent import
cycles.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from .signals import (
    BuiltinVersionSignal,
    FrameworkSignal,
    ManifestEntrySignal,
    ProviderDirSignal,
)

logger = logging.getLogger(__name__)

# Tool -> primary directory name mapping.  Kept here rather than imported from
# enums to avoid pulling the full enum module at import time; the mapping is
# stable and mirrors :class:`~vaultspec_core.core.enums.DirName`.
#: Shared with :mod:`vaultspec_core.core.diagnosis.collectors_content`.
TOOL_DIR: dict[str, str] = {
    "claude": ".claude",
    "gemini": ".gemini",
    "antigravity": ".agents",
    "codex": ".codex",
}
_SHARED_DIR_OWNERS: dict[str, set[str]] = {
    ".agents": {"antigravity", "gemini", "codex"},
}

# Host-tool-native files that legitimately live inside a provider directory but
# are owned by the host tool, not by vaultspec. Their presence must not classify
# a provider directory as MIXED (issue #122): a real Claude Code / Codex
# workspace always carries these, and the bundled spec-check hook runs
# ``spec doctor`` on every markdown commit, so treating them as foreign content
# blocked all markdown commits with no in-workspace remedy. ``"*"`` entries
# apply to every provider.
_HOST_NATIVE_FILES: dict[str, set[str]] = {
    "*": {".gitignore"},
    "claude": {"settings.json", "settings.local.json"},
    "codex": {"config.toml"},
}


def _is_host_native(tool_value: str, name: str) -> bool:
    """Return whether ``name`` is a benign host-tool-native provider file."""
    return name in _HOST_NATIVE_FILES.get("*", set()) or name in _HOST_NATIVE_FILES.get(
        tool_value, set()
    )


_tool_dir_validated = False


def _validate_tool_dir() -> None:
    """Verify ``TOOL_DIR`` covers every Tool member.

    Called once on first use to catch drift between the mapping and the enum.
    """
    global _tool_dir_validated
    if _tool_dir_validated:
        return

    from ..enums import Tool

    enum_values = {t.value for t in Tool}
    mapping_keys = set(TOOL_DIR)
    if mapping_keys != enum_values:
        missing = enum_values - mapping_keys
        extra = mapping_keys - enum_values
        raise RuntimeError(
            f"TOOL_DIR is out of sync with Tool enum: missing={missing} extra={extra}"
        )
    _tool_dir_validated = True


@lru_cache(maxsize=1)
def _framework_content_names() -> frozenset[str]:
    """Return the top-level ``.vaultspec/`` entry names the package seeds.

    Derived from the bundled builtin tree so the set of names that identify a
    real framework directory has exactly one source of truth and cannot drift
    into a second hand-maintained list as new resource categories ship.
    """
    from ...builtins import list_builtins

    return frozenset(rel.split("/", 1)[0] for rel in list_builtins())


def _carries_framework_content(fw_dir: Path) -> bool:
    """Return whether *fw_dir* holds recognizable vaultspec framework content.

    A directory that merely exists proves nothing; one that carries at least one
    of the resource categories the package seeds is a real framework tree whose
    runtime manifest is simply absent.
    """
    try:
        present = {child.name for child in fw_dir.iterdir()}
    except OSError as exc:
        logger.warning("Cannot read framework directory %s: %s", fw_dir, exc)
        return False
    return bool(present & _framework_content_names())


def collect_framework_presence(target: Path) -> FrameworkSignal:
    """Check whether the vaultspec framework directory is present and valid.

    Distinguishes a legitimately unmanifested workspace from a corrupt one. The
    runtime manifest is gitignored and per-machine by design, so its complete
    absence alongside real framework content is the expected shape of a fresh
    clone that tracks its canonical ``.vaultspec/`` tree - that is
    :attr:`~vaultspec_core.core.diagnosis.signals.FrameworkSignal.ADOPTABLE`,
    not corruption. A manifest that exists but cannot be parsed, or a framework
    directory carrying no recognizable content at all, remains
    :attr:`~vaultspec_core.core.diagnosis.signals.FrameworkSignal.CORRUPTED`.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.FrameworkSignal`
        reflecting the observed state.
    """
    fw_dir = target / ".vaultspec"
    if not fw_dir.exists():
        return FrameworkSignal.MISSING

    manifest_path = fw_dir / "providers.json"
    if not manifest_path.exists():
        if _carries_framework_content(fw_dir):
            return FrameworkSignal.ADOPTABLE
        return FrameworkSignal.CORRUPTED

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read manifest %s: %s", manifest_path, exc)
        return FrameworkSignal.CORRUPTED

    if "installed" not in raw:
        return FrameworkSignal.CORRUPTED

    return FrameworkSignal.PRESENT


def collect_manifest_coherence(target: Path) -> dict[str, ManifestEntrySignal]:
    """Compare the manifest's installed set against provider directories on disk.

    Args:
        target: Workspace root directory.

    Returns:
        Mapping of :class:`~vaultspec_core.core.enums.Tool` value strings to
        :class:`~vaultspec_core.core.diagnosis.signals.ManifestEntrySignal`.
    """
    from ..enums import Tool
    from ..manifest import read_manifest_data

    _validate_tool_dir()

    manifest = read_manifest_data(target)
    result: dict[str, ManifestEntrySignal] = {}

    for tool in Tool:
        dir_name = TOOL_DIR.get(tool.value)
        if dir_name is None:
            continue

        in_manifest = tool.value in manifest.installed
        dir_exists = (target / dir_name).is_dir()
        shared_owners = _SHARED_DIR_OWNERS.get(dir_name, set())
        shared_owner_installed = bool(shared_owners & manifest.installed)

        if in_manifest and dir_exists:
            result[tool.value] = ManifestEntrySignal.COHERENT
        elif in_manifest and not dir_exists:
            result[tool.value] = ManifestEntrySignal.ORPHANED
        elif not in_manifest and dir_exists and shared_owner_installed:
            result[tool.value] = ManifestEntrySignal.NOT_INSTALLED
        elif not in_manifest and dir_exists:
            result[tool.value] = ManifestEntrySignal.UNTRACKED
        else:
            result[tool.value] = ManifestEntrySignal.NOT_INSTALLED

    return result


def _provider_children(target: Path, tool_value: str) -> list[Path] | None:
    """Return the entries of a provider's directory.

    Args:
        target: Workspace root directory.
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        The directory's entries, or ``None`` when the provider has no known
        directory, the directory does not exist, or it cannot be read.
    """
    dir_name = TOOL_DIR.get(tool_value)
    if dir_name is None:
        return None

    provider_dir = target / dir_name
    if not provider_dir.exists():
        return None

    try:
        return list(provider_dir.iterdir())
    except OSError as exc:
        logger.warning("Cannot read provider directory %s: %s", provider_dir, exc)
        return None


def collect_provider_dir_state(target: Path, tool_value: str) -> ProviderDirSignal:
    """Assess the completeness of a provider's configuration directory.

    Args:
        target: Workspace root directory.
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.ProviderDirSignal`
        reflecting the observed state.
    """
    from ..enums import Tool
    from ..types import get_context

    children = _provider_children(target, tool_value)
    if children is None:
        return ProviderDirSignal.MISSING

    if not children:
        return ProviderDirSignal.EMPTY

    # Resolve expected subdirectories from ToolConfig
    tool = Tool(tool_value)
    try:
        ctx = get_context()
        cfg = ctx.tool_configs.get(tool)
    except LookupError:
        cfg = None

    if cfg is None:
        # Without config we cannot assess completeness beyond non-empty
        return ProviderDirSignal.PARTIAL

    # Content directories require markdown files; structural directories
    # (like workflows) only need to exist.
    content_dirs: list[Path] = []
    for d in (cfg.rules_dir, cfg.skills_dir, cfg.agents_dir):
        if d is not None:
            content_dirs.append(d)

    structural_dirs: list[Path] = []
    if cfg.workflows_dir is not None:
        structural_dirs.append(cfg.workflows_dir)

    expected_dirs = content_dirs + structural_dirs

    # Build a set of known paths to detect foreign content
    known_paths: set[Path] = set()
    for d in expected_dirs:
        known_paths.add(d)

    # Config files are also known content
    if cfg.config_file is not None:
        known_paths.add(cfg.config_file)
    if cfg.native_config_file is not None:
        known_paths.add(cfg.native_config_file)
    if cfg.system_file is not None:
        known_paths.add(cfg.system_file)
    # The provider-native MCP config (e.g. Antigravity's .agents/mcp_config.json)
    # is written by mcp_sync. Read the same ToolConfig field the writer uses so
    # the doctor and the writer share one notion of what legitimately lives in a
    # provider directory, rather than maintaining a divergent hardcoded list.
    if cfg.mcp_config_file is not None:
        known_paths.add(cfg.mcp_config_file)

    all_present = True
    for d in content_dirs:
        if not d.is_dir():
            all_present = False
            continue
        # Rules/agents dirs contain flat .md files; skills dirs contain
        # subdirectories each holding a SKILL.md.  Accept either layout.
        md_files = list(d.glob("*.md"))
        skill_files = list(d.glob("*/SKILL.md")) if not md_files else []
        if not md_files and not skill_files:
            all_present = False
    for d in structural_dirs:
        if not d.is_dir():
            all_present = False

    # Check for files in the provider directory that don't match known patterns
    has_foreign = False
    for child in children:
        child_resolved = child.resolve()
        # Known subdirectory
        if any(child_resolved == kp.resolve() for kp in known_paths):
            continue
        # Known config file at provider level
        if child.is_file() and any(
            child_resolved == kp.resolve() for kp in known_paths
        ):
            continue
        # Subdirectories of expected dirs are fine
        if child.is_dir() and any(child_resolved == d.resolve() for d in expected_dirs):
            continue
        # Host-tool-native files (e.g. Claude Code's settings.local.json) are
        # benign and must not classify the directory as MIXED (issue #122).
        if child.is_file() and _is_host_native(tool_value, child.name):
            continue
        # Advisory-lock byproducts (e.g. mcp_config.json.lock) are local runtime
        # artefacts the framework itself writes; they are not foreign content.
        if child.is_file() and child.name.endswith(".lock"):
            continue
        # If we reach here, the child is not a known resource
        has_foreign = True
        break

    if has_foreign:
        return ProviderDirSignal.MIXED

    return ProviderDirSignal.COMPLETE if all_present else ProviderDirSignal.PARTIAL


def collect_builtin_version_state(target: Path) -> BuiltinVersionSignal:
    """Check whether built-in resource snapshots are current.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.BuiltinVersionSignal`
        reflecting the observed state.
    """
    from ..revert import list_modified_builtins

    vaultspec_dir = target / ".vaultspec"
    snapshots_dir = vaultspec_dir / "_snapshots"

    results = list_modified_builtins(vaultspec_dir)

    if not results and not snapshots_dir.exists():
        return BuiltinVersionSignal.NO_SNAPSHOTS

    for entry in results:
        if entry["status"] == "missing":
            return BuiltinVersionSignal.DELETED

    for entry in results:
        if entry["status"] == "modified":
            return BuiltinVersionSignal.MODIFIED

    return BuiltinVersionSignal.CURRENT
