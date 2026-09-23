"""Render and reconcile vaultspec-core's managed pre-commit hooks.

Covers the mode-parameterized canonical hook definitions (entry prefix, hook
metadata, and the derived canonical hook list/entry map) plus the
``.pre-commit-config.yaml`` scaffolding and stripping logic that keeps a
project's hook file in sync with them.
"""

from __future__ import annotations

import io
import logging
from contextlib import nullcontext
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from ruamel.yaml import YAML, YAMLError

from .enums import InstallMode, PrecommitHook, render_mode
from .helpers import advisory_lock, atomic_write
from .prek_boundary import (
    PrekBoundaryState,
    collect_prek_boundary,
    existing_precommit_configs,
    precommit_config_path,
)
from .workspace_mode import (
    CORE_DISTRIBUTION_NAME,
    read_hooks_declaration,
    resolve_render_mode,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ALL_MANAGED_HOOK_IDS",
    "CANONICAL_ENTRY_PREFIX",
    "CANONICAL_HOOK_ENTRIES",
    "CANONICAL_HOOK_IDS",
    "CANONICAL_PRECOMMIT_HOOKS",
    "RETIRED_HOOK_IDS",
    "HookChange",
    "YamlHookAssessment",
    "assess_precommit_yaml",
    "canonical_hook_entries_for_mode",
    "canonical_precommit_hooks_for_mode",
    "entry_prefix_for_mode",
    "hook_defs_for_mode",
    "managed_strip_outcome",
    "scaffold_precommit",
    "strip_managed_precommit_hooks",
]


def _as_mapping(value: object) -> dict[str, Any] | None:
    """Narrow *value* to a plain dict, or ``None`` when it isn't one.

    A thin wrapper around ``isinstance(value, dict)``: narrowing an
    honestly-``Any`` YAML payload via a bare ``isinstance(x, dict)`` only
    recovers ``dict[Unknown, Unknown]``, so every downstream ``.get()`` stays
    partially unknown until the result is re-typed here.
    """
    if isinstance(value, dict):
        return cast("dict[str, Any]", value)
    return None


def _as_list(value: object) -> list[Any] | None:
    """Narrow *value* to a plain list, or ``None`` when it isn't one.

    See :func:`_as_mapping` - the same bare-``isinstance`` narrowing gap
    applies to lists pulled out of a YAML payload.
    """
    if isinstance(value, list):
        return cast("list[Any]", value)
    return None


# The canonical CLI-invocation prefix each pre-commit hook entry is built from,
# keyed by provisioning mode. Dependency mode resolves ``vaultspec-core`` through
# the target project's own venv via ``uv run`` (byte-identical to the single
# prefix that existed before mode-awareness); tool mode resolves it through an
# ephemeral ``uvx`` invocation so it never enters the project's dependency set.
_MODE_ENTRY_PREFIX: dict[InstallMode, str] = {
    InstallMode.DEPENDENCY: "uv run --no-sync vaultspec-core",
    InstallMode.TOOL: "uvx --from vaultspec-core vaultspec-core",
}


def entry_prefix_for_mode(mode: InstallMode) -> str:
    """Return the canonical hook-entry command prefix for *mode*.

    The lookup is keyed by the *rendered* mode (via
    :func:`~vaultspec_core.core.enums.render_mode`), so
    :attr:`~vaultspec_core.core.enums.InstallMode.DEV` resolves to the same
    ``uv run`` prefix as :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY`
    rather than needing its own table entry. This keeps the prefix table a
    two-shape render surface even as the mode vocabulary carries the third
    dev-scoped bookkeeping member.
    """
    return _MODE_ENTRY_PREFIX[render_mode(mode)]


#: Backward-compatible module-level prefix, pinned to dependency mode. Modules
#: and diagnostics that still assume a single prefix (the doctor's
#: canonical-entry check) read this until they are made mode-aware; the
#: mode-parameterized renderers derive their prefix from
#: :func:`entry_prefix_for_mode` instead.
CANONICAL_ENTRY_PREFIX = entry_prefix_for_mode(InstallMode.DEPENDENCY)


# Mode-independent pre-commit hook metadata: the CLI subcommand each hook
# invokes plus its non-entry pre-commit fields. The ``entry`` is derived per
# mode by prefixing the subcommand with the mode's canonical entry prefix. The
# insertion order here is the order hooks are scaffolded into
# ``.pre-commit-config.yaml`` and must be preserved.
_HOOK_SUBCOMMAND: dict[PrecommitHook, str] = {
    # A pure gate, never ``--fix``: a hook-time fix writes changes nobody
    # reviewed into commits that are not about them, and the hook runner's
    # revert-based staging protocol makes hook-time tree mutation unsafe in
    # shared worktrees.
    PrecommitHook.COMMIT_GATE: "commit-gate",
}
_HOOK_META: dict[PrecommitHook, dict[str, object]] = {
    # ``always_run`` so the per-machine file guard sees every commit, not only
    # those touching markdown; the gate itself ignores paths it has no rule for.
    PrecommitHook.COMMIT_GATE: {"name": "Vaultspec commit gate", "always_run": True},
}


def hook_defs_for_mode(mode: InstallMode) -> dict[PrecommitHook, dict[str, object]]:
    """Return the hook-field map for *mode*, keyed by :class:`PrecommitHook`.

    Each value merges the mode-independent metadata (name, filter fields) with
    an ``entry`` built from the mode's canonical prefix and the hook's
    subcommand, so dependency mode renders ``uv run --no-sync vaultspec-core
    ...`` and tool mode renders ``uvx --from vaultspec-core vaultspec-core
    ...``.
    """
    prefix = entry_prefix_for_mode(mode)
    defs: dict[PrecommitHook, dict[str, object]] = {}
    for hook, meta in _HOOK_META.items():
        # Preserve the original field order (name, entry, then the hook's
        # filter field) so the scaffolded YAML is byte-stable across modes.
        value: dict[str, object] = {"name": meta["name"]}
        value["entry"] = f"{prefix} {_HOOK_SUBCOMMAND[hook]}"
        for key, field in meta.items():
            if key != "name":
                value[key] = field
        defs[hook] = value
    return defs


def canonical_precommit_hooks_for_mode(mode: InstallMode) -> list[dict[str, object]]:
    """Return the full canonical pre-commit hook list rendered for *mode*."""
    return [
        {
            "id": hook.value,
            **meta,
            "language": "system",
            # The gate checks exactly the staged files the runner passes, which
            # is what keeps its cost proportional to the commit.
            "pass_filenames": True,
        }
        for hook, meta in hook_defs_for_mode(mode).items()
    ]


def canonical_hook_entries_for_mode(mode: InstallMode) -> dict[str, str]:
    """Return each canonical hook ID mapped to its expected entry for *mode*."""
    return {
        hook.value: str(meta["entry"])
        for hook, meta in hook_defs_for_mode(mode).items()
    }


CANONICAL_HOOK_IDS: frozenset[str] = frozenset(h.value for h in PrecommitHook)

#: Backward-compatible module-level canonical hooks and entries, pinned to
#: dependency mode. The doctor's canonical-entry check still imports
#: ``CANONICAL_HOOK_ENTRIES`` and compares against the single dependency-mode
#: shape; making that check mode-aware is the next phase. ``scaffold_precommit``
#: renders through :func:`canonical_precommit_hooks_for_mode` instead.
CANONICAL_PRECOMMIT_HOOKS: list[dict[str, object]] = canonical_precommit_hooks_for_mode(
    InstallMode.DEPENDENCY
)
CANONICAL_HOOK_ENTRIES: dict[str, str] = canonical_hook_entries_for_mode(
    InstallMode.DEPENDENCY
)

#: Hook IDs vaultspec-core once scaffolded and no longer renders. Existing
#: installs still carry them, so the scaffold removes them and uninstall still
#: strips them.
#:
#: ``vault-sanitize-annotations`` rewrote the whole vault from inside a commit,
#: contradicting the pure-gate rule above. ``vault-fix``, ``spec-check`` and
#: ``check-provider-artifacts`` each spent a process, and the first two a
#: vault-sized scan, on every commit; ``commit-gate`` does their commit-scoped
#: work in one process, and the whole-vault checks run in CI and on demand.
RETIRED_HOOK_IDS: frozenset[str] = frozenset(
    {
        "vault-sanitize-annotations",
        "vault-fix",
        "spec-check",
        "check-provider-artifacts",
    }
)

# All managed hook IDs for uninstall filtering.
ALL_MANAGED_HOOK_IDS: frozenset[str] = CANONICAL_HOOK_IDS | RETIRED_HOOK_IDS


def _precommit_yaml() -> YAML:
    """Return a round-trip YAML handler for ``.pre-commit-config.yaml``.

    Round-trip mode preserves the parts of an author-maintained config that a
    plain ``safe_load`` + ``dump`` cycle would silently rewrite: explanatory
    comments, the single-quoted literal form of ``exclude``/``files`` regexes,
    and long ``entry`` scalars that a re-emitter would otherwise line-wrap.
    Preserving them is what makes a full ``sync`` over a correctly-rendered
    config a byte-for-byte no-op instead of a spurious diff.

    The sequence indent is pinned to the non-indented block style
    (``sequence=2, offset=0``) so a freshly scaffolded config matches the
    historical layout, and ``width`` is raised so entry scalars are never
    folded onto continuation lines.
    """
    handler = YAML()
    handler.preserve_quotes = True
    handler.width = 4096
    handler.indent(mapping=2, sequence=2, offset=0)
    return handler


def _dump_precommit_yaml(handler: YAML, data: dict[str, Any]) -> str:
    """Serialise *data* to a string through the round-trip *handler*."""
    buffer = io.StringIO()
    handler.dump(data, buffer)
    return buffer.getvalue()


def _drop_managed_hook_entries(repos: list[Any]) -> bool:
    """Delete vaultspec-managed hooks from the ``repos`` sequence in place.

    Mutates the loaded structure so surviving non-vaultspec hooks keep their
    comments and quoting, and drops any local repo left without hooks.

    Returns:
        ``True`` when a managed hook was deleted.
    """
    changed = False
    for r in list(repos):
        record = _as_mapping(r)
        if record is None or record.get("repo") != "local":
            continue
        hooks = _as_list(record.get("hooks", []))
        if hooks is None:
            continue
        managed_idx = [
            i
            for i, h in enumerate(hooks)
            if (hook := _as_mapping(h)) is not None
            and hook.get("id") in ALL_MANAGED_HOOK_IDS
        ]
        for i in reversed(managed_idx):
            del hooks[i]
        if managed_idx:
            changed = True
        if not hooks:
            repos.remove(r)
    return changed


def managed_strip_outcome(
    config_file: Path,
) -> Literal["delete", "rewrite", "unchanged", "unreadable"]:
    """Report what :func:`strip_managed_precommit_hooks` would do, writing nothing.

    Returns:
        ``"delete"`` when only managed hooks (and nothing else) would remain to
        remove, ``"rewrite"`` when managed hooks would be stripped and other
        content kept, ``"unchanged"`` when the config parsed and carries
        nothing managed, and ``"unreadable"`` when it could not be read or
        parsed - kept apart from ``"unchanged"`` so no caller mistakes a
        config nobody could read for a clean one.
    """
    handler = _precommit_yaml()
    try:
        data = _as_mapping(handler.load(config_file.read_text(encoding="utf-8")))
    except (YAMLError, OSError, UnicodeDecodeError):
        return "unreadable"
    if data is None:
        return "unchanged"
    repos = _as_list(data.get("repos", []))
    if repos is None or not _drop_managed_hook_entries(repos):
        return "unchanged"
    if repos or len(data) > 1:
        return "rewrite"
    return "delete"


def strip_managed_precommit_hooks(config_file: Path) -> bool:
    """Remove vaultspec-managed hooks from an existing ``.pre-commit-config.yaml``.

    The file is rewritten in place, or deleted when nothing but the managed
    hooks remained.  Read, parse, and write failures are absorbed: uninstall
    residue removal is best-effort and never fails the run.

    Returns:
        ``True`` when the config was rewritten or deleted.
    """
    handler = _precommit_yaml()
    try:
        loaded: object = handler.load(config_file.read_text(encoding="utf-8"))
        data = _as_mapping(loaded)
        if data is None:
            return False
        repos = _as_list(data.get("repos", []))
        if repos is None:
            return False
        if not _drop_managed_hook_entries(repos):
            return False

        if repos:
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
            return True
        del data["repos"]
        if data:
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
        else:
            config_file.unlink()
    # UnicodeDecodeError subclasses ValueError, not OSError, so a file that
    # exists and cannot be decoded escaped this net and surfaced as a raw
    # traceback (issue #407).
    except (YAMLError, OSError, UnicodeDecodeError):
        return False
    return True


def _log_prek_boundary_status(target: Path, boundary: PrekBoundaryState) -> None:
    """Log why ``.pre-commit-config.yaml`` scaffolding is being skipped.

    Distinguishes a healthy transplant (the canonical hooks already live in
    ``prek.toml``) from stranded hooks that ``spec precommit migrate`` still
    needs to move, and flags a co-present, now-superseded YAML config in
    either case.
    """
    leftovers = existing_precommit_configs(target)
    if boundary.hooks_present:
        logger.info(
            "prek.toml at %s already carries the vaultspec-core hooks; "
            "skipping .pre-commit-config.yaml scaffold.",
            target,
        )
        if leftovers:
            logger.info(
                "A superseded YAML hook config is still present at %s. "
                "prek reads prek.toml exclusively; remove the YAML config "
                "once nothing else consumes it.",
                target,
            )
        return
    logger.info(
        "prek.toml detected at %s; skipping .pre-commit-config.yaml "
        "scaffold. Run 'vaultspec-core spec precommit migrate' to "
        "transplant the vaultspec-core hooks into prek.toml.",
        target,
    )
    if leftovers:
        logger.warning(
            "Both prek.toml and a YAML hook config are present at "
            "%s and prek.toml lacks the vaultspec-core hooks. prek "
            "reads prek.toml exclusively; vaultspec will not refresh "
            "the YAML hooks. Run 'vaultspec-core spec precommit "
            "migrate' to transplant them.",
            target,
        )


def _parse_precommit_config(config_file: Path, handler: YAML) -> tuple[bool, object]:
    """Read and parse *config_file* with the round-trip *handler*.

    Returns:
        ``(readable, loaded)``: ``readable`` is ``False`` when the file could
        not be read, decoded or parsed; ``loaded`` is the parsed document
        (``{}`` for an empty file) when it could.
    """
    try:
        raw = config_file.read_text(encoding="utf-8")
        return True, handler.load(raw) or {}
    # UnicodeDecodeError subclasses ValueError, not OSError, so a file that
    # exists and cannot be decoded escaped this net and surfaced as a raw
    # traceback (issue #407).
    except (YAMLError, OSError, UnicodeDecodeError):
        return False, None


def _as_config_mapping(loaded: object) -> dict[str, Any] | None:
    """Return *loaded* as a config mapping with a list ``repos``, or ``None``.

    ``None`` means a shape the reconcile does not recognise, which tells a
    writer to leave the file alone rather than risk corrupting it.
    """
    data = _as_mapping(loaded)
    if data is None:
        return None
    if _as_list(data.setdefault("repos", [])) is None:
        return None
    return data


def _load_existing_precommit_config(
    config_file: Path, handler: YAML
) -> dict[str, Any] | None:
    """Load and validate an existing ``.pre-commit-config.yaml``.

    Returns:
        The parsed mapping, with its ``repos`` key defaulted to a list, or
        ``None`` when the file cannot be read/parsed, isn't a mapping, or its
        ``repos`` key isn't list-shaped - any of which tells the caller to
        skip scaffolding for this run rather than risk corrupting a config
        it doesn't recognize.
    """
    readable, loaded = _parse_precommit_config(config_file, handler)
    return _as_config_mapping(loaded) if readable else None


class HookChange(StrEnum):
    """One reason the reconcile would rewrite a hook config.

    The reconcile reports these instead of logging as it goes, so a reader can
    ask what a writer would do - and why - without the writer's side effects.
    """

    ADDED = "added"
    UPDATED = "updated"
    RETIRED = "retired"
    DEDUPLICATED = "deduplicated"


_CHANGE_LOG: dict[HookChange, tuple[int, str]] = {
    HookChange.ADDED: (logging.INFO, "Added pre-commit hook '%s'"),
    HookChange.UPDATED: (
        logging.INFO,
        "Updated pre-commit hook '%s' entry to canonical pattern",
    ),
    HookChange.RETIRED: (logging.INFO, "Removed retired pre-commit hook '%s'"),
    HookChange.DEDUPLICATED: (
        logging.WARNING,
        "Removed duplicate pre-commit hook '%s'; it was listed more than once "
        "and would have run on every commit twice",
    ),
}


def _merge_local_repo_hooks(
    local_hook_lists: list[list[Any]], canonical_hooks: list[dict[str, object]]
) -> list[tuple[HookChange, str]]:
    """Reconcile every local repo's hooks against *canonical_hooks* in place.

    All ``repo: local`` entries are considered together, because prek runs
    each of them: hooks whose ID is in :data:`RETIRED_HOOK_IDS` are removed
    wherever they sit; a canonical hook listed more than once keeps only its
    first entry, since every copy would run again on each commit; a canonical
    hook present anywhere has a drifted entry updated in place; and one present
    nowhere is appended to the first local repo.

    Args:
        local_hook_lists: The ``hooks`` list of each local repo, in file order.
        canonical_hooks: The canonical hook mappings to reconcile against.

    Returns:
        Each change made, with the hook id it concerns, in the order made.
    """
    changes: list[tuple[HookChange, str]] = []
    canonical_ids = {str(hook["id"]) for hook in canonical_hooks}
    first_by_id: dict[str, dict[str, Any]] = {}
    for hooks in local_hook_lists:
        for i in reversed(range(len(hooks))):
            hook = _as_mapping(hooks[i])
            if hook is not None and hook.get("id") in RETIRED_HOOK_IDS:
                changes.append((HookChange.RETIRED, str(hook.get("id"))))
                del hooks[i]
    for hooks in local_hook_lists:
        kept: list[Any] = []
        for raw_hook in hooks:
            hook = _as_mapping(raw_hook)
            hook_id = str(hook.get("id")) if hook is not None else None
            if hook is not None and hook_id in canonical_ids:
                if hook_id in first_by_id:
                    changes.append((HookChange.DEDUPLICATED, hook_id))
                    continue
                first_by_id[hook_id] = hook
            kept.append(raw_hook)
        hooks[:] = kept
    for canonical in canonical_hooks:
        hook_id = str(canonical["id"])
        existing = first_by_id.get(hook_id)
        if existing is None:
            local_hook_lists[0].append(dict(canonical))
            changes.append((HookChange.ADDED, hook_id))
            continue
        if existing.get("entry") == canonical["entry"]:
            continue
        existing["entry"] = canonical["entry"]
        changes.append((HookChange.UPDATED, hook_id))
    return changes


def _reconcile_precommit_repos(
    data: dict[str, Any], canonical_hooks: list[dict[str, object]]
) -> list[tuple[HookChange, str]] | None:
    """Reconcile the local repos' hooks in *data* against *canonical_hooks*.

    Creates a local repo when none exists; otherwise merges via
    :func:`_merge_local_repo_hooks` and drops any local repo the merge emptied.

    Returns:
        The changes made to *data* (empty when it already matches), or
        ``None`` when a local repo's ``hooks`` is not a list, which leaves the
        config unrecognised and *data* untouched.
    """
    repos = cast("list[Any]", data["repos"])
    local_repos = [
        rec
        for r in repos
        if (rec := _as_mapping(r)) is not None and rec.get("repo") == "local"
    ]
    if not local_repos:
        repos.append({"repo": "local", "hooks": [dict(h) for h in canonical_hooks]})
        return [(HookChange.ADDED, str(h["id"])) for h in canonical_hooks]

    hook_lists: list[list[Any]] = []
    for local_repo in local_repos:
        hooks = _as_list(local_repo.setdefault("hooks", []))
        if hooks is None:
            return None
        hook_lists.append(hooks)
    had_hooks = [bool(hooks) for hooks in hook_lists]
    changes = _merge_local_repo_hooks(hook_lists, canonical_hooks)
    # Only a repo the merge itself emptied goes: an empty stanza the operator
    # wrote is theirs, and one the merge emptied is residue vaultspec created.
    for local_repo, hooks, had in zip(local_repos, hook_lists, had_hooks, strict=True):
        if had and not hooks:
            repos.remove(local_repo)
    return changes


def _managed_local_hooks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the vaultspec-managed hook mappings across every local repo."""
    hooks: list[dict[str, Any]] = []
    for raw_repo in cast("list[Any]", data["repos"]):
        repo = _as_mapping(raw_repo)
        if repo is None or repo.get("repo") != "local":
            continue
        for raw_hook in _as_list(repo.get("hooks", [])) or []:
            hook = _as_mapping(raw_hook)
            if hook is not None and hook.get("id") in ALL_MANAGED_HOOK_IDS:
                hooks.append(hook)
    return hooks


@dataclass(frozen=True)
class YamlHookAssessment:
    """What the YAML hook config prek would read says, and what a sync would do.

    Built by the same parse and the same reconcile the scaffold writes with,
    so every reader - doctor, sync's stand-down decision, uninstall, mode
    detection - reaches the verdict the writer would, rather than a parallel
    one that could drift from it.

    Attributes:
        config: The YAML config prek would read.
        exists: The config exists.
        readable: It could be read and parsed.
        recognised: It parsed to a shape the reconcile works on.
        vaultspec_hooks: It lists at least one vaultspec hook, current or
            retired, in a local repo.
        changes: What the scaffold would change, in order; empty when it
            already matches the canonical set.
        canonical_entries: The ``entry`` of each canonical-id hook as found,
            in file order.
    """

    config: Path
    exists: bool
    readable: bool = False
    recognised: bool = False
    vaultspec_hooks: bool = False
    changes: tuple[tuple[HookChange, str], ...] = ()
    canonical_entries: tuple[str, ...] = ()

    @property
    def change_kinds(self) -> frozenset[HookChange]:
        """The distinct kinds of change the scaffold would make."""
        return frozenset(kind for kind, _hook_id in self.changes)


def assess_precommit_yaml(
    target: Path, *, mode: InstallMode | None = None
) -> YamlHookAssessment:
    """Assess the YAML hook config prek would read at *target*, writing nothing.

    Args:
        target: Workspace root directory.
        mode: Provisioning mode to render canonical entries for; resolved from
            the workspace declaration when ``None``, as the scaffold does.

    Returns:
        The :class:`YamlHookAssessment` for the effective config.
    """
    config = precommit_config_path(target)
    if not config.exists():
        return YamlHookAssessment(config=config, exists=False)
    readable, loaded = _parse_precommit_config(config, _precommit_yaml())
    if not readable:
        return YamlHookAssessment(config=config, exists=True)
    data = _as_config_mapping(loaded)
    if data is None:
        return YamlHookAssessment(config=config, exists=True, readable=True)
    managed = _managed_local_hooks(data)
    entries = tuple(
        str(h.get("entry", "")) for h in managed if h.get("id") in CANONICAL_HOOK_IDS
    )
    if mode is None:
        mode = resolve_render_mode(target, package=CORE_DISTRIBUTION_NAME)
    changes = _reconcile_precommit_repos(data, canonical_precommit_hooks_for_mode(mode))
    return YamlHookAssessment(
        config=config,
        exists=True,
        readable=True,
        recognised=changes is not None,
        vaultspec_hooks=bool(managed),
        changes=tuple(changes or ()),
        canonical_entries=entries,
    )


def scaffold_precommit(
    target: Path, *, dry_run: bool = False, mode: InstallMode | None = None
) -> list[tuple[str, str]]:
    """Scaffold or merge vaultspec-core hooks into .pre-commit-config.yaml.

    Ensures the full canonical hook set is present with canonical entry
    patterns.  Existing hooks with matching IDs are updated to the
    canonical entry; missing hooks are appended.

    The file is the one prek would read
    (:func:`~vaultspec_core.core.prek_boundary.precommit_config_path`): an
    existing ``.pre-commit-config.yml`` is managed in place rather than joined
    by a ``.yaml`` that would take precedence over it.

    The entry each hook is rendered with follows the resolved provisioning
    mode: dependency mode keeps the ``uv run --no-sync vaultspec-core`` prefix,
    tool mode uses ``uvx --from vaultspec-core vaultspec-core``. When *mode* is
    ``None`` it is resolved from the committed workspace declaration via
    :func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`, whose
    legacy-absent rule renders dependency mode so a workspace provisioned
    before ``install-mode`` keeps its existing hook entries. The fresh-install
    caller passes its resolved mode explicitly, because the declaration is
    written only after scaffolding.

    Skips scaffolding entirely in two cases.

    The first is a committed opt-out: a workspace whose declaration sets
    ``hooks.pre_commit`` to ``false`` has decided it runs its gates explicitly
    and forbids a commit hook, so no install or sync writes the file. The
    declaration is read on every call rather than resolved once at provision
    time, so the choice survives every later run instead of being re-decided by
    whichever verb happens to reach here.

    The second is ``prek.toml`` being present at *target* (assessed through
    :func:`~vaultspec_core.core.prek_boundary.collect_prek_boundary`):
    prek reads ``prek.toml`` exclusively and silently ignores a co-present
    ``.pre-commit-config.yaml``, so writing the YAML would leave hooks prek
    never runs. The operator transplants hooks into ``prek.toml`` with
    ``spec precommit migrate``; the log messages distinguish a healthy
    transplant (hooks already in ``prek.toml``) from stranded hooks.

    Neither skip deletes an existing ``.pre-commit-config.yaml``. Declining
    future scaffolding is a policy statement; removing a file the operator may
    still have reasons to keep is a destructive act they ask for explicitly.
    """
    if not read_hooks_declaration(target).pre_commit:
        logger.info(
            "The workspace declaration at %s sets hooks.pre_commit to false; "
            "skipping .pre-commit-config.yaml scaffolding.",
            target,
        )
        return []

    if mode is None:
        mode = resolve_render_mode(target, package=CORE_DISTRIBUTION_NAME)
    canonical_hooks = canonical_precommit_hooks_for_mode(mode)

    boundary = collect_prek_boundary(target, mode=mode)
    if boundary.owns_boundary:
        _log_prek_boundary_status(target, boundary)
        return []

    config_file = precommit_config_path(target)
    handler = _precommit_yaml()
    result = [(config_file.name, "precommit")]

    with nullcontext() if dry_run else advisory_lock(config_file):
        if not config_file.exists():
            if not dry_run:
                data = {
                    "repos": [
                        {"repo": "local", "hooks": [dict(h) for h in canonical_hooks]}
                    ]
                }
                atomic_write(config_file, _dump_precommit_yaml(handler, data))
            return result

        data = _load_existing_precommit_config(config_file, handler)
        if data is None:
            return []
        changes = _reconcile_precommit_repos(data, canonical_hooks)
        if not changes:
            return []

        if not dry_run:
            atomic_write(config_file, _dump_precommit_yaml(handler, data))
            # Logged only once the write has happened: the reconcile reports
            # its changes rather than logging them, so readers can run it too.
            for kind, hook_id in changes:
                level, message = _CHANGE_LOG[kind]
                logger.log(level, message, hook_id)
        return result
