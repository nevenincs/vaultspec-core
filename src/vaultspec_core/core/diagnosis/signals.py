"""Signal enums for workspace and provider diagnosis.

Each enum encodes the observable state of a single diagnostic axis.
:class:`ResolutionAction` maps diagnosed states to corrective operations.
"""

from __future__ import annotations

from enum import StrEnum

from ..home import ProcessRegistrySignal as ProcessRegistrySignal


class FrameworkSignal(StrEnum):
    """Observed state of the vaultspec framework directory.

    ``ADOPTABLE`` separates a legitimately unmanifested workspace from a
    genuinely broken one. ``.vaultspec/providers.json`` is gitignored and
    per-machine by design, so a fresh clone of a project that tracks its
    canonical framework content carries the content but no runtime manifest.
    Folding that state into ``CORRUPTED`` forced adoption through ``--force``,
    which overwrites the very content the clone was tracking.
    """

    MISSING = "missing"
    CORRUPTED = "corrupted"
    ADOPTABLE = "adoptable"
    PRESENT = "present"


class ProviderDirSignal(StrEnum):
    """Observed state of a provider's configuration directory."""

    MISSING = "missing"
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"
    MIXED = "mixed"


class ManifestEntrySignal(StrEnum):
    """Coherence between a provider directory and the manifest."""

    COHERENT = "coherent"
    ORPHANED = "orphaned"
    UNTRACKED = "untracked"
    NOT_INSTALLED = "not_installed"


class ContentSignal(StrEnum):
    """Content integrity of a managed resource file."""

    CLEAN = "clean"
    DIVERGED = "diverged"
    STALE = "stale"
    MISSING = "missing"


class BuiltinVersionSignal(StrEnum):
    """Version state of built-in resource snapshots."""

    CURRENT = "current"
    MODIFIED = "modified"
    DELETED = "deleted"
    NO_SNAPSHOTS = "no_snapshots"


class ConfigSignal(StrEnum):
    """Observed state of a provider's root configuration file.

    ``UNREADABLE`` says the check could not run: the file is present and
    could not be parsed. It is distinct from ``PARTIAL_MCP``, which is the
    benign reading for a file that parsed fine and simply carries no
    ``mcpServers`` mapping - conflating the two let a corrupt ``.mcp.json``
    read as merely incomplete (issue #407).
    """

    OK = "ok"
    MISSING = "missing"
    FOREIGN = "foreign"
    PARTIAL_MCP = "partial_mcp"
    USER_MCP = "user_mcp"
    REGISTRY_DRIFT = "registry_drift"
    UNREADABLE = "unreadable"


class GitignoreSignal(StrEnum):
    """Observed state of gitignore entries for managed paths.

    ``UNMANAGED`` is the degraded reading of ``NO_FILE`` and ``NO_ENTRIES``:
    the same absence, observed in a workspace where vaultspec is installed and
    has not been told to stay out. Those two remain the benign readings for a
    workspace that never asked for management or opted out of it, and they stay
    informational; ``UNMANAGED`` is weighed, because a workspace whose
    per-machine artefacts nothing ignores is the condition this check exists to
    catch.

    ``UNREADABLE`` is not a state of the subject at all: it says the check
    could not run. A collector that fails must not report the value it would
    have reported had it run and found nothing wrong - that is how a broken
    workspace came to read as a healthy one (issue #407). Weighed as a
    warning, because a check that did not run cannot vouch for anything.
    """

    NO_FILE = "no_file"
    NO_ENTRIES = "no_entries"
    UNMANAGED = "unmanaged"
    UNREADABLE = "unreadable"
    PARTIAL = "partial"
    COMPLETE = "complete"
    CORRUPTED = "corrupted"


class GitattributesSignal(StrEnum):
    """Observed state of gitattributes entries for managed paths.

    ``UNMANAGED`` carries the same meaning as its
    :class:`GitignoreSignal` counterpart: the block is absent, or could not be
    read, in a workspace that is installed and has not declined it. The other
    two absences stay benign for a workspace that never asked or has declared
    it does not want the block.

    ``UNREADABLE`` is not a state of the subject at all: it says the check
    could not run. A collector that fails must not report the value it would
    have reported had it run and found nothing wrong - that is how a broken
    workspace came to read as a healthy one (issue #407). Weighed as a
    warning, because a check that did not run cannot vouch for anything.
    """

    NO_FILE = "no_file"
    NO_ENTRIES = "no_entries"
    UNMANAGED = "unmanaged"
    UNREADABLE = "unreadable"
    PARTIAL = "partial"
    COMPLETE = "complete"
    CORRUPTED = "corrupted"


class PrecommitSignal(StrEnum):
    """Observed state of pre-commit hooks for vaultspec-core.

    Every member but :attr:`NOT_INSTALLED` describes the *configuration*.
    A configuration can be perfect and still run nothing, which is what
    :attr:`NOT_INSTALLED` reports: git has no ``pre-commit`` hook, so the
    declared hooks never execute on a commit.

    ``UNREADABLE`` says the config vouches for nothing: either the check could
    not run, or the config lists vaultspec hooks in a shape the scaffold will
    not rewrite, so no writer maintains them. A collector that fails must not
    report the value it would have reported had it run and found nothing
    wrong - that is how a broken workspace came to read as a healthy one
    (issue #407). Weighed as a warning, because such a config cannot vouch for
    anything.

    ``DECLINED`` and ``DECLINED_LEFTOVER`` report a workspace whose committed
    declaration sets ``hooks.pre_commit`` to ``false``. Neither is a fault:
    the workspace chose to run its gates explicitly, so the absence of the
    canonical hooks is the requested state. ``DECLINED_LEFTOVER`` adds that a
    ``.pre-commit-config.yaml`` is still on disk, which the operator may want
    to delete by hand.

    ``DUPLICATED`` is an error: the config prek reads lists a canonical hook
    more than once (or carries more than one managed block), so prek would run
    it repeatedly on every commit. ``SHADOWED`` is a warning: vaultspec hooks
    sit in a config file prek does not read, because another config takes
    precedence, so they look configured and never run.
    """

    NO_FILE = "no_file"
    NO_HOOKS = "no_hooks"
    INCOMPLETE = "incomplete"
    NON_CANONICAL = "non_canonical"
    UNREFRESHABLE = "unrefreshable"
    ORPHANED = "orphaned"
    NOT_INSTALLED = "not_installed"
    UNREADABLE = "unreadable"
    DECLINED = "declined"
    DECLINED_LEFTOVER = "declined_leftover"
    DUPLICATED = "duplicated"
    SHADOWED = "shadowed"
    COMPLETE = "complete"


class VaultContentSignal(StrEnum):
    """Observed state of generated vault document annotations."""

    NO_VAULT = "no_vault"
    CLEAN = "clean"
    ANNOTATIONS = "annotations"
    UNREADABLE = "unreadable"


class RenameIntegritySignal(StrEnum):
    """Observed state of resource name/filename integrity."""

    CLEAN = "clean"
    MISMATCH = "mismatch"
    ERROR = "error"


class ModeMismatchSignal(StrEnum):
    """Coherence between the persisted install mode and observed artifacts.

    Compares the mode named by the committed ``.vaultspec/workspace.json``
    declaration against the shape of the provisioned artifacts (the canonical
    pre-commit hook entries and the ``.mcp.json`` launch command).

    Members:
        CLEAN: The declaration and the observed artifacts agree, or there is
            nothing to compare against.
        MISMATCH: The declaration names one mode but the artifacts are shaped
            for the other, e.g. ``uv run`` hook entries in a workspace whose
            declaration names tool mode.
        UNKNOWN: No mode is persisted (the legacy pre-``install-mode`` bridge
            case); there is no declared mode to hold the artifacts against, so
            this is not a warning.
    """

    CLEAN = "clean"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class VersionFloorSignal(StrEnum):
    """State of the running version against the committed floor constraint.

    Members:
        OK: The running version is at or above the declared
            ``minimum_vaultspec_version``, or the workspace declares no floor.
        BELOW: The running version is strictly below the declared floor. On
            install and sync this is a refuse-and-tell error; on doctor it is
            reported as an error-weighted row without raising.
    """

    OK = "ok"
    BELOW = "below"


class ProviderHookSignal(StrEnum):
    """Agreement between one provider's rendered hooks and their source.

    The subject is a single hook-capable provider: whether what
    ``.vaultspec/hooks/`` currently renders for it is what its native
    hook-config file carries, and whether the ownership record that lets a
    re-sync remove its own entries and nobody else's is intact.

    ``NO_SOURCES`` and ``IN_SYNC`` are the two benign readings, and they say
    different things: the first that there is nothing to render, the second
    that everything that should be rendered is. ``UNREADABLE`` says the check
    could not run, and is weighed as a warning rather than folded into
    ``IN_SYNC``, because a collector that failed cannot vouch for agreement.

    Members:
        NO_SOURCES: The workspace declares no hooks this provider could
            consume, and the provider carries none.
        IN_SYNC: Every group the current source renders is present, and the
            ownership record matches it exactly.
        UNTRUSTED: Every hook this provider would render is awaiting operator
            approval, so the renderer skipped it. Benign: a hook that does not
            render because nobody approved it is the consent gate working, and
            a sync will not change it. The remedy is a decision, not a command.
        NOT_RENDERED: The source renders groups for this provider and none of
            them reached its config file. Ordinarily an un-run sync, or one
            run with ``--skip hooks``.
        STALE: The config file carries some but not all of what the source
            renders, or carries managed entries the source no longer renders.
        SIDECAR_MISSING: The rendered groups are all present but no ownership
            record accompanies them, so a re-sync can no longer tell its own
            entries from hand-authored ones.
        SIDECAR_STALE: An ownership record is present and disagrees with what
            the source renders, so a re-sync would prune the wrong entries.
        UNREADABLE: The config file or the ownership record is present and
            could not be parsed.
    """

    NO_SOURCES = "no_sources"
    IN_SYNC = "in_sync"
    UNTRUSTED = "untrusted"
    NOT_RENDERED = "not_rendered"
    STALE = "stale"
    SIDECAR_MISSING = "sidecar_missing"
    SIDECAR_STALE = "sidecar_stale"
    UNREADABLE = "unreadable"


class ResolutionAction(StrEnum):
    """Corrective action that a resolver can apply."""

    SCAFFOLD = "scaffold"
    SYNC = "sync"
    PRUNE = "prune"
    REPAIR_MANIFEST = "repair_manifest"
    ADOPT_DIRECTORY = "adopt_directory"
    ADOPT_FRAMEWORK = "adopt_framework"
    REPAIR_GITIGNORE = "repair_gitignore"
    REPAIR_GITATTRIBUTES = "repair_gitattributes"
    REPAIR_PRECOMMIT = "repair_precommit"
    REMOVE = "remove"
    SKIP = "skip"
