"""Pre-commit hook boundary collectors.

Assesses the state of vaultspec-core hooks, whether they are boundary-owned by
``prek.toml`` or still declared in ``.pre-commit-config.yaml``, and which
install mode a deployed hook entry's canonical shape observes. All imports
from ``core.*`` modules are deferred inside function bodies to prevent import
cycles.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .signals import PrecommitSignal

if TYPE_CHECKING:
    from ..enums import InstallMode
    from ..precommit import YamlHookAssessment
    from ..prek_boundary import PrekBoundaryState

logger = logging.getLogger(__name__)

# ``observed_precommit_mode`` is consumed by :mod:`.collectors_mode` (the
# mode-mismatch collector) and re-exported by :mod:`.collectors`.


def collect_precommit_state(target: Path) -> PrecommitSignal:
    """Assess the state of vaultspec-core hooks in ``.pre-commit-config.yaml``.

    Doctor implements no hook check of its own here. The YAML side maps the
    scaffold's own assessment
    (:func:`~vaultspec_core.core.precommit.assess_precommit_yaml`) onto a
    signal, and the prek side maps the boundary assessment
    (:func:`~vaultspec_core.core.prek_boundary.collect_prek_boundary`) the
    same way, so what doctor reports and what the repair verbs do can never
    disagree. When ``prek.toml``
    is present the hook scaffold never runs, so the boundary is assessed
    through
    :func:`~vaultspec_core.core.prek_boundary.collect_prek_boundary` and
    the signal reflects ``prek.toml``'s contents rather than its mere
    existence:

    - canonical hooks present in ``prek.toml`` and no YAML config left
      behind:
      :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.COMPLETE`;
    - canonical hooks present in ``prek.toml`` with a superseded
      ``.pre-commit-config.yaml`` still on disk:
      :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.ORPHANED`
      (benign; prek silently ignores the YAML);
    - canonical hooks absent from ``prek.toml`` (including an unparseable
      ``prek.toml``):
      :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.UNREFRESHABLE`
      - the hooks are genuinely stranded, whatever the YAML says, because
      prek never reads it and sync will not refresh it. The remediation is
      ``spec precommit migrate``.

    A committed opt-out (``hooks.pre_commit`` set to ``false``) is read first
    and outranks every configuration reading above: the workspace declined the
    hooks, so their absence from either file is the requested state, not
    stranding. The signal is
    :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.DECLINED`,
    or
    :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.DECLINED_LEFTOVER`
    when a YAML hook config (``.yaml`` or ``.yml``) is still on disk. Nothing is
    deleted.

    Two cross-config readings sit on top: ``DUPLICATED`` when the config prek
    reads lists a canonical hook more than once (an error, since prek would run
    it repeatedly), and ``SHADOWED`` when vaultspec hooks sit in a config prek
    does not read while the live one is sound (a warning, since they look
    configured and never run). A leftover YAML beside a healthy ``prek.toml``
    that carries no vaultspec hooks stays ``ORPHANED``.

    The YAML config read is the one prek would read, per
    :func:`~vaultspec_core.core.prek_boundary.precommit_config_path`.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal`
        reflecting the observed state.

    Raises:
        VaultSpecError: If the workspace declaration is malformed.
    """
    from ..prek_boundary import collect_prek_boundary, existing_precommit_configs
    from ..workspace_mode import read_hooks_declaration

    if not read_hooks_declaration(target).pre_commit:
        if existing_precommit_configs(target):
            return PrecommitSignal.DECLINED_LEFTOVER
        return PrecommitSignal.DECLINED

    boundary = collect_prek_boundary(target)
    if not boundary.owns_boundary:
        return _yaml_side_state(target)
    return _prek_side_state(target, boundary)


def _yaml_side_state(target: Path) -> PrecommitSignal:
    """Assess a workspace whose hooks live in a YAML config."""
    from ..precommit import assess_precommit_yaml
    from ..prek_boundary import existing_precommit_configs

    assessment = assess_precommit_yaml(target)
    signal = _reassess_against_installation(target, _yaml_signal(assessment))
    unread = [c for c in existing_precommit_configs(target) if c != assessment.config]
    if signal in _HEALTHY and any(_carries_vaultspec_hooks(c) for c in unread):
        return PrecommitSignal.SHADOWED
    return signal


def _yaml_signal(assessment: YamlHookAssessment) -> PrecommitSignal:
    """Name, as a signal, what the scaffold would do to the live YAML config.

    A pure mapping: whether the config exists, parses and carries vaultspec
    hooks, and which changes the scaffold's own reconcile reports, all come
    from :func:`~vaultspec_core.core.precommit.assess_precommit_yaml`. Doctor
    therefore reaches the verdict the writer would, and a repair it plans is
    one the writer will actually make.
    """
    from ..precommit import HookChange

    if not assessment.exists:
        return PrecommitSignal.NO_FILE
    if not assessment.readable:
        return PrecommitSignal.UNREADABLE
    if not assessment.vaultspec_hooks:
        return PrecommitSignal.NO_HOOKS
    kinds = assessment.change_kinds
    if HookChange.DEDUPLICATED in kinds:
        return PrecommitSignal.DUPLICATED
    if kinds & {HookChange.ADDED, HookChange.RETIRED}:
        return PrecommitSignal.INCOMPLETE
    if HookChange.UPDATED in kinds:
        return PrecommitSignal.NON_CANONICAL
    return PrecommitSignal.COMPLETE


def _prek_side_state(target: Path, boundary: PrekBoundaryState) -> PrecommitSignal:
    """Assess a workspace whose hook boundary ``prek.toml`` owns."""
    from ..prek_boundary import existing_precommit_configs

    if boundary.duplicated:
        return PrecommitSignal.DUPLICATED
    if not boundary.hooks_present:
        return PrecommitSignal.UNREFRESHABLE
    leftovers = existing_precommit_configs(target)
    if any(_carries_vaultspec_hooks(c) for c in leftovers):
        return PrecommitSignal.SHADOWED
    if leftovers:
        return PrecommitSignal.ORPHANED
    return _reassess_against_installation(target, PrecommitSignal.COMPLETE)


#: Signals a shadowed copy may displace: the live config is otherwise sound,
#: so the copy prek ignores is the one thing left to report. A signal naming
#: a fault in the live config stays, as the more urgent finding.
_HEALTHY = (PrecommitSignal.COMPLETE, PrecommitSignal.NOT_INSTALLED)


def _carries_vaultspec_hooks(config: Path) -> bool:
    """Whether *config* lists any vaultspec hook, current or retired."""
    from ..precommit import managed_strip_outcome

    return managed_strip_outcome(config) in ("delete", "rewrite")


def _hooks_directory(target: Path) -> Path | None:
    """Return the directory git runs hooks from, or ``None`` if unknowable.

    Git is asked rather than assuming ``<target>/.git/hooks``, because that
    assumption is wrong in two ordinary layouts: ``core.hooksPath`` relocates
    the directory outright, and a linked worktree keeps its hooks in the
    common git directory rather than beside its own gitdir.

    Args:
        target: Workspace root directory.

    Returns:
        The resolved hooks directory, or ``None`` when *target* is not a git
        working tree or git is not on ``PATH``.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        logger.debug("Cannot resolve the git hooks directory for %s: %s", target, exc)
        return None

    printed = result.stdout.strip()
    if not printed:
        return None
    return (target / printed).resolve()


def precommit_hook_installed(target: Path) -> bool | None:
    """Whether git has a ``pre-commit`` hook installed for *target*.

    Args:
        target: Workspace root directory.

    Returns:
        ``True`` or ``False``, or ``None`` when the question cannot be
        answered - *target* is not a git working tree, or git is unavailable.
        ``None`` is deliberately distinct from ``False``: hooks are not
        stranded merely because this could not look.
    """
    hooks_directory = _hooks_directory(target)
    if hooks_directory is None:
        return None
    return (hooks_directory / "pre-commit").is_file()


def _reassess_against_installation(
    target: Path, signal: PrecommitSignal
) -> PrecommitSignal:
    """Report a complete configuration that nothing will run as such.

    Only :attr:`~vaultspec_core.core.diagnosis.signals.PrecommitSignal.COMPLETE`
    is reassessed. Every other signal already names a fault in the
    configuration itself, and that fault is both more actionable and the thing
    to fix first; an uninstalled hook stacked on a broken config is not a
    second finding worth displacing the first.

    Args:
        target: Workspace root directory.
        signal: The verdict reached from the configuration alone.

    Returns:
        ``NOT_INSTALLED`` when a complete configuration has no installed hook
        to run it, and *signal* unchanged otherwise.
    """
    if signal is not PrecommitSignal.COMPLETE:
        return signal
    if precommit_hook_installed(target) is False:
        return PrecommitSignal.NOT_INSTALLED
    return signal


def observed_precommit_mode(
    target: Path, package: str | None = None
) -> InstallMode | None:
    """Infer the install mode the deployed hook entries are shaped for.

    Reads the canonical hook entries from the same assessment of the YAML
    config the scaffold and doctor use
    (:func:`~vaultspec_core.core.precommit.assess_precommit_yaml`).
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
    from ..commands import entry_prefix_for_mode
    from ..enums import InstallMode
    from ..precommit import assess_precommit_yaml
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, canonical_distribution_name

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME
    if canonical_distribution_name(pkg) != CORE_DISTRIBUTION_NAME:
        return None

    entries = assess_precommit_yaml(target).canonical_entries

    # Longest prefix first so tool mode's "uvx --from vaultspec-core
    # vaultspec-core" is tested before any shorter prefix could partial-match.
    prefixes = sorted(
        ((entry_prefix_for_mode(m), m) for m in InstallMode),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )

    observed: set[InstallMode] = set()
    for entry in entries:
        for prefix, mode in prefixes:
            if entry.startswith(prefix):
                observed.add(mode)
                break

    if len(observed) == 1:
        return next(iter(observed))
    return None
