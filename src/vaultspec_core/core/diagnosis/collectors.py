"""Signal collectors for workspace and provider diagnosis.

Each collector examines a single diagnostic axis and returns the appropriate
:mod:`~vaultspec_core.core.diagnosis.signals` enum value.  All imports from
``core.*`` modules are deferred inside function bodies to prevent import cycles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .signals import (
    BuiltinVersionSignal,
    ConfigSignal,
    ContentSignal,
    FrameworkSignal,
    GitattributesSignal,
    GitignoreSignal,
    ManifestEntrySignal,
    ModeMismatchSignal,
    PrecommitSignal,
    ProviderDirSignal,
    RenameIntegritySignal,
    VaultContentSignal,
    VersionFloorSignal,
)

if TYPE_CHECKING:
    from ..enums import InstallMode

logger = logging.getLogger(__name__)

# Tool -> primary directory name mapping.  Kept here rather than imported from
# enums to avoid pulling the full enum module at import time; the mapping is
# stable and mirrors :class:`~vaultspec_core.core.enums.DirName`.
_TOOL_DIR: dict[str, str] = {
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
    """Verify ``_TOOL_DIR`` covers every Tool member.

    Called once on first use to catch drift between the mapping and the enum.
    """
    global _tool_dir_validated
    if _tool_dir_validated:
        return

    from ..enums import Tool

    enum_values = {t.value for t in Tool}
    mapping_keys = set(_TOOL_DIR)
    if mapping_keys != enum_values:
        missing = enum_values - mapping_keys
        extra = mapping_keys - enum_values
        raise RuntimeError(
            f"_TOOL_DIR is out of sync with Tool enum: missing={missing} extra={extra}"
        )
    _tool_dir_validated = True


def collect_framework_presence(target: Path) -> FrameworkSignal:
    """Check whether the vaultspec framework directory is present and valid.

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
        dir_name = _TOOL_DIR.get(tool.value)
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

    dir_name = _TOOL_DIR.get(tool_value)
    if dir_name is None:
        return ProviderDirSignal.MISSING

    provider_dir = target / dir_name
    if not provider_dir.exists():
        return ProviderDirSignal.MISSING

    # Check if directory is empty
    try:
        children = list(provider_dir.iterdir())
    except OSError as exc:
        logger.warning("Cannot read provider directory %s: %s", provider_dir, exc)
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
        if any(child_resolved == kp.resolve() for kp in known_paths if kp is not None):
            continue
        # Known config file at provider level
        if child.is_file() and any(
            child_resolved == kp.resolve() for kp in known_paths if kp is not None
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

    if all_present:
        return ProviderDirSignal.COMPLETE

    return ProviderDirSignal.PARTIAL


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


def collect_config_state(tool_value: str) -> ConfigSignal:
    """Assess the state of a provider's root configuration file.

    Args:
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.ConfigSignal`
        reflecting the observed state.
    """
    from ..enums import Tool
    from ..types import get_context

    tool = Tool(tool_value)

    try:
        ctx = get_context()
        cfg = ctx.tool_configs.get(tool)
    except LookupError:
        return ConfigSignal.MISSING

    if cfg is None:
        return ConfigSignal.MISSING

    config_file = cfg.config_file
    if config_file is None:
        return ConfigSignal.MISSING

    if not config_file.exists():
        return ConfigSignal.MISSING

    try:
        content = config_file.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read config %s: %s", config_file, exc)
        return ConfigSignal.MISSING

    # Detect both legacy AUTO-GENERATED header and current <vaultspec> tags
    if "AUTO-GENERATED" in content or "<vaultspec " in content:
        return ConfigSignal.OK

    return ConfigSignal.FOREIGN


def collect_mcp_config_state(target: Path) -> ConfigSignal:
    """Assess the state of the ``.mcp.json`` MCP configuration.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.ConfigSignal`
        reflecting the observed MCP configuration state.
    """
    mcp_path = target / ".mcp.json"
    if not mcp_path.exists():
        return ConfigSignal.PARTIAL_MCP

    try:
        raw = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read MCP config %s: %s", mcp_path, exc)
        return ConfigSignal.PARTIAL_MCP

    if not isinstance(raw, dict):
        return ConfigSignal.PARTIAL_MCP

    servers = raw.get("mcpServers")
    if not isinstance(servers, dict):
        return ConfigSignal.PARTIAL_MCP

    # Check registry drift: compare deployed entries against definitions
    # rendered for the workspace's resolved mode. The seeded builtin carries
    # mode-neutral placeholder tokens, so an unrendered registry entry can never
    # equal the rendered .mcp.json launch and would report drift on every
    # workspace. resolve_render_mode's legacy-absent rule keeps a pre-install-mode
    # workspace on the dependency-shaped expectation.
    from ..mcps import collect_mcp_servers
    from ..workspace_mode import resolve_render_mode

    registry = collect_mcp_servers(mode=resolve_render_mode(target), target=target)
    if registry:
        managed_names = set(registry.keys())
        for name, (_path, expected_config) in registry.items():
            if name not in servers:
                return ConfigSignal.REGISTRY_DRIFT
            if servers[name] != expected_config:
                return ConfigSignal.REGISTRY_DRIFT

        has_user_entries = bool(set(servers.keys()) - managed_names)
        if has_user_entries:
            return ConfigSignal.USER_MCP
        return ConfigSignal.OK

    # Fallback when no registry is available (pre-registry workspace)
    if "vaultspec-core" not in servers:
        return ConfigSignal.PARTIAL_MCP

    if len(servers) > 1:
        return ConfigSignal.USER_MCP

    return ConfigSignal.OK


def collect_vault_content_state(target: Path) -> tuple[VaultContentSignal, int, int]:
    """Assess generated template annotations in ``.vault/`` without mutating.

    This collector intentionally avoids the vault scanner because scanner access
    can trigger lazy migrations. Doctor must remain a read-only signal surface.

    Args:
        target: Workspace root directory.

    Returns:
        ``(signal, annotated_document_count, unreadable_markdown_count)``.
    """
    from ...config import get_config
    from ...vaultcore.checks.annotations import strip_template_annotations

    vault_dir = target / get_config().docs_dir
    if not vault_dir.is_dir():
        return VaultContentSignal.NO_VAULT, 0, 0

    annotated = 0
    unreadable = 0
    for path in sorted(vault_dir.rglob("*.md")):
        if ".obsidian" in path.parts or "_archive" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue

        _cleaned, stats = strip_template_annotations(content)
        if stats.total:
            annotated += 1

    if annotated:
        return VaultContentSignal.ANNOTATIONS, annotated, unreadable
    if unreadable:
        return VaultContentSignal.UNREADABLE, annotated, unreadable
    return VaultContentSignal.CLEAN, annotated, unreadable


def collect_gitignore_state(target: Path) -> GitignoreSignal:
    """Assess the state of vaultspec-managed ``.gitignore`` entries.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.GitignoreSignal`
        reflecting the observed state.
    """
    from ..gitignore import _find_markers, get_recommended_entries

    gi_path = target / ".gitignore"
    if not gi_path.exists():
        return GitignoreSignal.NO_FILE

    try:
        content = gi_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read .gitignore %s: %s", gi_path, exc)
        return GitignoreSignal.NO_FILE

    lines = [line.strip() for line in content.splitlines()]
    begins, ends = _find_markers(lines)

    if not begins and not ends:
        return GitignoreSignal.NO_ENTRIES

    # Any state that isn't exactly one BEGIN before exactly one END is corrupted.
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return GitignoreSignal.CORRUPTED

    begin_idx = begins[0]
    end_idx = ends[0]
    block_entries = [
        line.rstrip() for line in lines[begin_idx + 1 : end_idx] if line.strip()
    ]

    # Contradictory check: is an entry in the block explicitly unignored elsewhere?
    # (i.e. starts with "!")
    unignored = {line[1:].strip() for line in lines if line.startswith("!")}
    for entry in block_entries:
        if entry in unignored or entry.rstrip("/") in unignored:
            return GitignoreSignal.CORRUPTED

    # The managed block lists only runtime by-products; authored content
    # is team-shared (cli-spec-gitignore ADR). The recommended set no
    # longer varies by source-repo mode, so the diagnosis compares against
    # one canonical shape.
    recommended = get_recommended_entries(target)

    # Check if all recommended entries are present in the block.
    # We allow extra entries (idempotency is handled by ensure_gitignore_block).
    if all(entry in block_entries for entry in recommended):
        return GitignoreSignal.COMPLETE

    return GitignoreSignal.PARTIAL


def collect_content_integrity(tool_value: str) -> dict[str, ContentSignal]:
    """Check content integrity of managed rule files for a provider.

    Verifies that each managed rule file exists at the provider's
    destination.

    Args:
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        Mapping of filename to
        :class:`~vaultspec_core.core.diagnosis.signals.ContentSignal`.
    """
    from ..enums import Tool
    from ..helpers import collect_md_resources
    from ..rules import transform_rule
    from ..sync import apply_file_sync
    from ..system import SYSTEM_BUILTIN_RULE
    from ..types import SyncResult, get_context

    tool = Tool(tool_value)
    result: dict[str, ContentSignal] = {}

    try:
        ctx = get_context()
        cfg = ctx.tool_configs.get(tool)
    except LookupError:
        return result

    if cfg is None or cfg.rules_dir is None:
        return result

    dest_dir = cfg.rules_dir
    source_dir = ctx.rules_src_dir

    # Content integrity is decided by the same comparator sync uses, not by
    # filename presence. The ambiguous-states resolver ADR specified that this
    # collector reuse the sync infrastructure and compare expected transformed
    # output against the actual destination; a prior name-only implementation
    # drifted from that, reporting a content-drifted file as CLEAN while sync
    # would rewrite it. We render each managed rule through the same
    # ``transform_rule`` the sync engine applies, then route it through
    # ``apply_file_sync`` in dry-run mode (no write) so the doctor's verdict and
    # sync's verdict come from one decision. Content drift now surfaces as
    # DIVERGED instead of a false CLEAN.
    #
    # Source rules are globbed read-only and reduced to their flat basename -
    # the same name the flat provider deployment carries. The recursive glob in
    # ``collect_md_resources`` discovers any project-authored source one level
    # down (#153) without the flattening side effect of ``collect_rules`` (the
    # doctor must not mutate the source tree).
    expected: dict[str, str] = {}
    if source_dir.is_dir():
        raw_sources = collect_md_resources(source_dir)
        for key, (_src_path, meta, body) in raw_sources.items():
            name = key.replace("\\", "/").rsplit("/", 1)[-1]
            expected[name] = transform_rule(tool, name, meta, body)

    dest_files: set[str] = set()
    if dest_dir.is_dir():
        dest_files = {f.name for f in dest_dir.glob("*.md")}

    # Files with a source: dry-run the canonical comparator and map its action.
    # [UNCHANGED] -> CLEAN, [UPDATE] -> DIVERGED, [ADD] (dest absent) -> MISSING.
    for name, content in expected.items():
        probe = SyncResult()
        action = apply_file_sync(probe, dest_dir / name, content, dry_run=True)
        if action == "[UNCHANGED]":
            result[name] = ContentSignal.CLEAN
        elif action == "[ADD]":
            result[name] = ContentSignal.MISSING
        else:  # [UPDATE]
            result[name] = ContentSignal.DIVERGED

    # Files only in destination: an orphan with no source (e.g. a retired
    # builtin's leftover deployment). The synthesized system rule has no source.
    for name in dest_files - set(expected):
        if name == SYSTEM_BUILTIN_RULE:
            continue  # Synthesized by system_sync(), not sourced
        result[name] = ContentSignal.STALE

    return result


def collect_gitattributes_state(target: Path) -> GitattributesSignal:
    """Assess the state of vaultspec-managed ``.gitattributes`` entries.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.GitattributesSignal`
        reflecting the observed state.
    """
    from ..gitattributes import DEFAULT_ENTRIES, _find_markers, has_valid_block

    ga_path = target / ".gitattributes"
    if not ga_path.exists():
        return GitattributesSignal.NO_FILE

    try:
        content = ga_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read .gitattributes %s: %s", ga_path, exc)
        return GitattributesSignal.NO_FILE

    lines = [line.strip() for line in content.splitlines()]
    begins, ends = _find_markers(lines)

    if not begins and not ends:
        return GitattributesSignal.NO_ENTRIES

    if not has_valid_block(lines):
        return GitattributesSignal.CORRUPTED

    begin_idx = begins[0]
    end_idx = ends[0]
    block_entries = [
        line.rstrip() for line in lines[begin_idx + 1 : end_idx] if line.strip()
    ]

    if all(entry in block_entries for entry in DEFAULT_ENTRIES):
        return GitattributesSignal.COMPLETE

    return GitattributesSignal.PARTIAL


def collect_precommit_state(target: Path) -> PrecommitSignal:
    """Assess the state of vaultspec-core hooks in ``.pre-commit-config.yaml``.

    Checks that all canonical hooks are present and use the canonical
    entry pattern (``uv run --no-sync vaultspec-core ...``).

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal`
        reflecting the observed state.
    """
    import yaml

    from ..commands import CANONICAL_HOOK_IDS, canonical_hook_entries_for_mode
    from ..workspace_mode import resolve_render_mode

    # Derive the expected hook entries from the workspace's resolved mode so a
    # correctly-provisioned tool-mode workspace (uvx entries) is not diagnosed
    # as non-canonical against the dependency-mode shape. resolve_render_mode's
    # legacy-absent rule keeps a pre-install-mode workspace on dependency-shaped
    # expectations. P04 layers a dedicated mode-mismatch signal on top of this.
    expected_entries = canonical_hook_entries_for_mode(resolve_render_mode(target))

    config_path = target / ".pre-commit-config.yaml"
    if not config_path.exists():
        return PrecommitSignal.NO_FILE

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Cannot read .pre-commit-config.yaml %s: %s", config_path, exc)
        return PrecommitSignal.NO_FILE

    if not isinstance(data, dict):
        return PrecommitSignal.NO_HOOKS

    repos = data.get("repos", [])
    if not isinstance(repos, list):
        return PrecommitSignal.NO_HOOKS

    # Collect all hooks from local repos
    local_hooks: list[dict[str, object]] = []
    for repo in repos:
        if isinstance(repo, dict) and repo.get("repo") == "local":
            hooks = repo.get("hooks", [])
            if isinstance(hooks, list):
                local_hooks.extend(h for h in hooks if isinstance(h, dict))

    found_ids = {
        str(h.get("id")) for h in local_hooks if h.get("id") in CANONICAL_HOOK_IDS
    }

    if not found_ids:
        return PrecommitSignal.NO_HOOKS

    if found_ids != CANONICAL_HOOK_IDS:
        return PrecommitSignal.INCOMPLETE

    # All hooks present - check entry patterns match exactly
    for hook in local_hooks:
        hook_id = hook.get("id")
        if hook_id in CANONICAL_HOOK_IDS:
            entry = str(hook.get("entry", ""))
            expected = expected_entries.get(str(hook_id), "")
            if entry != expected:
                return PrecommitSignal.NON_CANONICAL

    return PrecommitSignal.COMPLETE


def _observed_precommit_mode(
    target: Path, package: str | None = None
) -> InstallMode | None:
    """Infer the install mode the deployed hook entries are shaped for.

    Reads ``.pre-commit-config.yaml`` and inspects the canonical hook entries.
    Each mode renders a distinct entry prefix (``uv run --no-sync
    vaultspec-core`` for dependency mode, ``uvx --from vaultspec-core
    vaultspec-core`` for tool mode), so the prefix a deployed entry carries
    names the mode it was provisioned for. The prefixes are read from
    :func:`~vaultspec_core.core.commands.entry_prefix_for_mode`, the same source
    the renderer uses, so this never hardcodes a second copy of the shape.

    The pre-commit hooks are core's own artifact: they invoke ``vaultspec-core``
    regardless of which companion packages are provisioned, and a companion
    package scaffolds no hooks of its own. So for any *package* other than
    ``vaultspec-core`` this observes nothing (``None``) - that package's mode is
    observable only through its MCP launch, not through hooks it does not own.

    Args:
        target: Workspace root directory.
        package: Distribution name whose observed hook shape to read; ``None``
            means ``vaultspec-core``. Any other package returns ``None``.

    Returns:
        The single :class:`~vaultspec_core.core.enums.InstallMode` every
        canonical hook entry agrees on, or ``None`` when there is no config, no
        canonical hook, the entries disagree, or *package* is not core.
    """
    import yaml

    from ..commands import CANONICAL_HOOK_IDS, entry_prefix_for_mode
    from ..enums import InstallMode
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, _canonical_distribution_name

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME
    if _canonical_distribution_name(pkg) != CORE_DISTRIBUTION_NAME:
        return None

    config_path = target / ".pre-commit-config.yaml"
    if not config_path.exists():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Cannot read .pre-commit-config.yaml %s: %s", config_path, exc)
        return None
    if not isinstance(data, dict):
        return None
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        return None

    # Longest prefix first so tool mode's "uvx --from vaultspec-core
    # vaultspec-core" is tested before any shorter prefix could partial-match.
    prefixes = sorted(
        ((entry_prefix_for_mode(m), m) for m in InstallMode),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )

    observed: set[InstallMode] = set()
    for repo in repos:
        if not isinstance(repo, dict) or repo.get("repo") != "local":
            continue
        hooks = repo.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict) or hook.get("id") not in CANONICAL_HOOK_IDS:
                continue
            entry = str(hook.get("entry", ""))
            for prefix, mode in prefixes:
                if entry.startswith(prefix):
                    observed.add(mode)
                    break

    if len(observed) == 1:
        return next(iter(observed))
    return None


def _observed_mcp_mode(target: Path, package: str | None = None) -> InstallMode | None:
    """Infer the install mode *package*'s deployed MCP launch command is shaped for.

    Reads ``.mcp.json`` and matches *package*'s server entry (the server name is
    the distribution name) against the concrete launch each mode renders
    (dependency mode launches through ``uv run``, tool mode through ``uvx``). The
    runnable module is recovered from the deployed ``args`` (the token after
    ``-m``) and the two candidate shapes are reconstructed through the renderer's
    own :func:`~vaultspec_core.core.mcps.render_launch_for_mode`, so this matches
    against the single launch comparator rather than a second hardcoded copy and
    works for any package's module without a per-package table.

    Args:
        target: Workspace root directory.
        package: Distribution name whose server entry to read; ``None`` means
            ``vaultspec-core``. The server name in ``.mcp.json`` is this name.

    Returns:
        The matching :class:`~vaultspec_core.core.enums.InstallMode`, or ``None``
        when there is no config, no matching server entry, the module cannot be
        recovered, or the entry matches neither rendered launch shape.
    """
    from ..enums import InstallMode
    from ..mcps import render_launch_for_mode
    from ..workspace_mode import CORE_DISTRIBUTION_NAME

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME

    mcp_path = target / ".mcp.json"
    if not mcp_path.exists():
        return None
    try:
        raw = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read MCP config %s: %s", mcp_path, exc)
        return None
    if not isinstance(raw, dict):
        return None
    servers = raw.get("mcpServers")
    if not isinstance(servers, dict):
        return None
    entry = servers.get(pkg)
    if not isinstance(entry, dict):
        return None

    command = entry.get("command")
    args = entry.get("args")
    if not isinstance(args, list) or "-m" not in args:
        return None
    module_index = args.index("-m") + 1
    if module_index >= len(args):
        return None
    module = args[module_index]
    if not isinstance(module, str):
        return None

    for mode in (InstallMode.TOOL, InstallMode.DEPENDENCY):
        mode_command, mode_args = render_launch_for_mode(mode, pkg, module)
        if command == mode_command and args == mode_args:
            return mode
    return None


def collect_mode_mismatch_state(
    target: Path, package: str | None = None
) -> ModeMismatchSignal:
    """Compare *package*'s persisted install mode against its observed artifacts.

    Reads *package*'s own entry in the committed ``.vaultspec/workspace.json``
    declaration and holds the mode it names against the shape of that package's
    provisioned artifacts: for core, the canonical pre-commit hook entries and
    the ``.mcp.json`` launch command; for a companion package, only its own MCP
    launch. When a deployed artifact is shaped for a mode other than the declared
    one - a ``uv run`` hook entry or a non-``uvx`` MCP command in a workspace
    whose declaration names tool mode, or the reverse - the workspace is flagged
    :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.MISMATCH`
    with the fix hint pointing at ``install --upgrade`` or an explicit
    ``--mode`` re-run.

    The declared mode is compared through
    :func:`~vaultspec_core.core.enums.render_mode`, not raw, because that is the
    mode the artifacts actually render as: a declared-``dev`` package renders
    byte-identically to ``dependency``, so a ``dev`` declaration against
    dependency-shaped artifacts is coherent, not a mismatch. Without this
    collapse every ``dev``-mode workspace would falsely flag, since no artifact
    ever carries a distinct ``dev`` shape.

    A package with no persisted entry is
    :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.UNKNOWN`:
    it predates the ``install-mode`` decision (or is not provisioned), so there
    is no declared mode to hold its artifacts against and this is not a warning.
    Everything coherent - or a declared package whose artifacts cannot be read -
    is :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.CLEAN`.

    Args:
        target: Workspace root directory.
        package: Distribution name whose mode coherence to assess; ``None`` means
            ``vaultspec-core``.

    Returns:
        The observed
        :class:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal`.

    Raises:
        VaultSpecError: If the declaration exists but is malformed (propagated
            from
            :func:`~vaultspec_core.core.workspace_mode.read_package_declaration`).
    """
    from ..enums import render_mode
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, read_package_declaration

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME
    declaration = read_package_declaration(target, pkg)
    if declaration is None:
        return ModeMismatchSignal.UNKNOWN

    declared = render_mode(declaration.install_mode)
    observed = {
        mode
        for mode in (
            _observed_precommit_mode(target, pkg),
            _observed_mcp_mode(target, pkg),
        )
        if mode is not None
    }
    if any(mode != declared for mode in observed):
        return ModeMismatchSignal.MISMATCH
    return ModeMismatchSignal.CLEAN


def collect_version_floor_state(
    target: Path, package: str | None = None
) -> tuple[VersionFloorSignal, str, str]:
    """Evaluate *package*'s committed floor constraint for the doctor's read-only view.

    Runs the shared :func:`~vaultspec_core.core.workspace_mode.evaluate_version_floor`
    comparator - the same one the resolver's refuse-and-tell path uses - so the
    doctor reports exactly the condition install and sync refuse on. The running
    version tested is *package*'s own installed version, and the floor is
    *package*'s own entry in the shared map, so a companion package's floor is
    diagnosed against its own release rather than core's. Unlike the enforcement
    path, this never raises: a corrupt declaration or an unreadable version is
    treated as "no constraint" so the read-only doctor surface stays crash-free.

    Args:
        target: Workspace root directory.
        package: Distribution name whose floor to evaluate; ``None`` means
            ``vaultspec-core``.

    Returns:
        ``(signal, running_version, minimum_version)``. When the running
        version is below the floor the signal is
        :attr:`~vaultspec_core.core.diagnosis.signals.VersionFloorSignal.BELOW`
        and the two version strings are populated; otherwise the signal is
        :attr:`~vaultspec_core.core.diagnosis.signals.VersionFloorSignal.OK`
        with empty strings.
    """
    from importlib.metadata import version as pkg_version

    from ..exceptions import VaultSpecError
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, evaluate_version_floor

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME

    try:
        running = pkg_version(pkg)
    except Exception:
        logger.debug("Could not determine running version for floor state")
        return VersionFloorSignal.OK, "", ""

    try:
        violation = evaluate_version_floor(target, running, package=pkg)
    except VaultSpecError:
        logger.debug("Could not read declaration for floor state", exc_info=True)
        return VersionFloorSignal.OK, "", ""

    if violation is None:
        return VersionFloorSignal.OK, "", ""

    running_v, floor = violation
    return VersionFloorSignal.BELOW, running_v, floor


def collect_rename_integrity(target: Path) -> tuple[RenameIntegritySignal, int]:
    """Check name/filename integrity for rules, skills, and agents.

    Args:
        target: Workspace root directory.

    Returns:
        ``(signal, mismatch_count)``.
    """
    from ...vaultcore.checks import Severity
    from ...vaultcore.checks.rename_integrity import check_rename_integrity

    try:
        result = check_rename_integrity(target)
        mismatch_count = 0
        has_error = False

        for diag in result.diagnostics:
            if diag.severity == Severity.ERROR:
                if "does not match expected name" in diag.message:
                    mismatch_count += 1
                else:
                    has_error = True

        if has_error:
            return RenameIntegritySignal.ERROR, mismatch_count
        if mismatch_count > 0:
            return RenameIntegritySignal.MISMATCH, mismatch_count
        return RenameIntegritySignal.CLEAN, 0
    except Exception as exc:
        logger.warning("Rename integrity collector failed: %s", exc, exc_info=True)
        return RenameIntegritySignal.ERROR, 0
