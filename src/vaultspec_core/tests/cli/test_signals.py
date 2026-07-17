"""Tests for diagnosis signal enums and dataclasses."""

from __future__ import annotations

import pytest

from vaultspec_core.core.diagnosis.diagnosis import (
    ProviderDiagnosis,
    WorkspaceDiagnosis,
)
from vaultspec_core.core.diagnosis.signals import (
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
    ResolutionAction,
    VaultContentSignal,
    VersionFloorSignal,
)
from vaultspec_core.core.enums import CliAction, PrecommitHook, Tool

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize(
    ("enum_cls", "expected_members"),
    [
        (
            FrameworkSignal,
            {"MISSING", "CORRUPTED", "PRESENT"},
        ),
        (
            ProviderDirSignal,
            {"MISSING", "EMPTY", "PARTIAL", "COMPLETE", "MIXED"},
        ),
        (
            ManifestEntrySignal,
            {"COHERENT", "ORPHANED", "UNTRACKED", "NOT_INSTALLED"},
        ),
        (
            ContentSignal,
            {"CLEAN", "DIVERGED", "STALE", "MISSING"},
        ),
        (
            BuiltinVersionSignal,
            {"CURRENT", "MODIFIED", "DELETED", "NO_SNAPSHOTS"},
        ),
        (
            ConfigSignal,
            {"OK", "MISSING", "FOREIGN", "PARTIAL_MCP", "USER_MCP", "REGISTRY_DRIFT"},
        ),
        (
            GitignoreSignal,
            {"NO_FILE", "NO_ENTRIES", "PARTIAL", "COMPLETE", "CORRUPTED"},
        ),
        (
            GitattributesSignal,
            {"NO_FILE", "NO_ENTRIES", "PARTIAL", "COMPLETE", "CORRUPTED"},
        ),
        (
            PrecommitSignal,
            {
                "NO_FILE",
                "NO_HOOKS",
                "INCOMPLETE",
                "NON_CANONICAL",
                "UNREFRESHABLE",
                "COMPLETE",
            },
        ),
        (
            VaultContentSignal,
            {
                "NO_VAULT",
                "CLEAN",
                "ANNOTATIONS",
                "UNREADABLE",
            },
        ),
        (
            RenameIntegritySignal,
            {
                "CLEAN",
                "MISMATCH",
                "ERROR",
            },
        ),
        (
            PrecommitHook,
            {
                "VAULT_FIX",
                "VAULT_SANITIZE_ANNOTATIONS",
                "CHECK_PROVIDER_ARTIFACTS",
                "SPEC_CHECK",
            },
        ),
        (
            CliAction,
            {
                "INSTALL",
                "UPGRADE",
                "SYNC",
                "UNINSTALL",
                "DOCTOR",
            },
        ),
        (
            ResolutionAction,
            {
                "SCAFFOLD",
                "SYNC",
                "PRUNE",
                "REPAIR_MANIFEST",
                "ADOPT_DIRECTORY",
                "REPAIR_GITIGNORE",
                "REPAIR_GITATTRIBUTES",
                "REPAIR_PRECOMMIT",
                "REMOVE",
                "SKIP",
            },
        ),
    ],
)
def test_enum_members(enum_cls, expected_members):
    assert set(enum_cls.__members__) == expected_members


@pytest.mark.parametrize(
    ("enum_cls", "member", "value"),
    [
        (ResolutionAction, "SCAFFOLD", "scaffold"),
        (ResolutionAction, "SKIP", "skip"),
        (FrameworkSignal, "PRESENT", "present"),
        (GitignoreSignal, "NO_FILE", "no_file"),
        (RenameIntegritySignal, "CLEAN", "clean"),
    ],
)
def test_enum_string_values(enum_cls, member, value):
    assert enum_cls[member] == value
    assert enum_cls[member].value == value


class TestProviderDiagnosis:
    def test_construction_minimal(self):
        diag = ProviderDiagnosis(
            tool=Tool.CLAUDE,
            dir_state=ProviderDirSignal.COMPLETE,
            manifest_entry=ManifestEntrySignal.COHERENT,
        )
        assert diag.tool == Tool.CLAUDE
        assert diag.dir_state == ProviderDirSignal.COMPLETE
        assert diag.manifest_entry == ManifestEntrySignal.COHERENT
        assert diag.content == {}
        assert diag.config == ConfigSignal.OK

    def test_construction_full(self):
        content = {"rules.md": ContentSignal.DIVERGED}
        diag = ProviderDiagnosis(
            tool=Tool.GEMINI,
            dir_state=ProviderDirSignal.PARTIAL,
            manifest_entry=ManifestEntrySignal.ORPHANED,
            content=content,
            config=ConfigSignal.OK,
        )
        assert diag.content == content
        assert diag.config == ConfigSignal.OK


class TestWorkspaceDiagnosis:
    def test_construction_minimal(self):
        diag = WorkspaceDiagnosis(framework=FrameworkSignal.PRESENT)
        assert diag.framework == FrameworkSignal.PRESENT
        assert diag.providers == {}
        assert diag.builtin_version == BuiltinVersionSignal.NO_SNAPSHOTS
        assert diag.gitignore == GitignoreSignal.NO_FILE
        assert diag.gitattributes == GitattributesSignal.NO_FILE
        assert diag.vault_content == VaultContentSignal.NO_VAULT
        assert diag.vault_annotation_count == 0
        assert diag.vault_unreadable_count == 0
        assert diag.rename_integrity == RenameIntegritySignal.CLEAN
        assert diag.rename_mismatch_count == 0

    def test_construction_with_providers(self):
        prov = ProviderDiagnosis(
            tool=Tool.CLAUDE,
            dir_state=ProviderDirSignal.COMPLETE,
            manifest_entry=ManifestEntrySignal.COHERENT,
        )
        diag = WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            providers={Tool.CLAUDE: prov},
            builtin_version=BuiltinVersionSignal.CURRENT,
            gitignore=GitignoreSignal.COMPLETE,
        )
        assert Tool.CLAUDE in diag.providers
        assert diag.builtin_version == BuiltinVersionSignal.CURRENT
        assert diag.gitignore == GitignoreSignal.COMPLETE


class TestDoctorExitCode:
    """The doctor exit code must not block commits on soft signals (issue #122)."""

    def _clean_workspace(self, prov: ProviderDiagnosis) -> WorkspaceDiagnosis:
        return WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            providers={prov.tool: prov},
            builtin_version=BuiltinVersionSignal.CURRENT,
            gitignore=GitignoreSignal.COMPLETE,
            gitattributes=GitattributesSignal.COMPLETE,
            precommit=PrecommitSignal.COMPLETE,
            migration_status="up_to_date",
            vault_content=VaultContentSignal.CLEAN,
            rename_integrity=RenameIntegritySignal.CLEAN,
        )

    def test_mixed_provider_dir_does_not_fail_exit_code(self) -> None:
        """A MIXED provider directory is informational and must exit 0.

        A real Claude Code / Codex workspace always carries host-native files;
        before the fix, MIXED set has_warn and the doctor exited 1, which the
        bundled spec-check pre-commit hook turned into a blocked markdown commit.
        """
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        prov = ProviderDiagnosis(
            tool=Tool.CLAUDE,
            dir_state=ProviderDirSignal.MIXED,
            manifest_entry=ManifestEntrySignal.COHERENT,
        )
        assert _doctor_exit_code(self._clean_workspace(prov)) == 0

    def test_partial_provider_dir_still_warns(self) -> None:
        """PARTIAL remains a genuine warning - the fix is scoped to MIXED."""
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        prov = ProviderDiagnosis(
            tool=Tool.CLAUDE,
            dir_state=ProviderDirSignal.PARTIAL,
            manifest_entry=ManifestEntrySignal.COHERENT,
        )
        assert _doctor_exit_code(self._clean_workspace(prov)) == 1


class TestDoctorModeAndFloorWeighting:
    """Doctor weights the install-mode and floor signals correctly."""

    def _prov(self) -> ProviderDiagnosis:
        return ProviderDiagnosis(
            tool=Tool.CLAUDE,
            dir_state=ProviderDirSignal.COMPLETE,
            manifest_entry=ManifestEntrySignal.COHERENT,
        )

    def _workspace(
        self,
        *,
        mode_mismatch: ModeMismatchSignal = ModeMismatchSignal.CLEAN,
        version_floor: VersionFloorSignal = VersionFloorSignal.OK,
    ) -> WorkspaceDiagnosis:
        return WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            providers={Tool.CLAUDE: self._prov()},
            builtin_version=BuiltinVersionSignal.CURRENT,
            gitignore=GitignoreSignal.COMPLETE,
            gitattributes=GitattributesSignal.COMPLETE,
            precommit=PrecommitSignal.COMPLETE,
            migration_status="up_to_date",
            vault_content=VaultContentSignal.CLEAN,
            rename_integrity=RenameIntegritySignal.CLEAN,
            mode_mismatch=mode_mismatch,
            version_floor=version_floor,
        )

    def test_clean_mode_and_no_floor_exit_zero(self) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        assert _doctor_exit_code(self._workspace()) == 0

    def test_unknown_mode_is_not_a_warning(self) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        diag = self._workspace(mode_mismatch=ModeMismatchSignal.UNKNOWN)
        assert _doctor_exit_code(diag) == 0

    def test_mode_mismatch_warns(self) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        diag = self._workspace(mode_mismatch=ModeMismatchSignal.MISMATCH)
        assert _doctor_exit_code(diag) == 1

    def test_below_floor_is_an_error(self) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        diag = self._workspace(version_floor=VersionFloorSignal.BELOW)
        assert _doctor_exit_code(diag) == 2

    def test_below_floor_outranks_mode_warning(self) -> None:
        from vaultspec_core.cli.spec_cmd import _doctor_exit_code

        diag = self._workspace(
            mode_mismatch=ModeMismatchSignal.MISMATCH,
            version_floor=VersionFloorSignal.BELOW,
        )
        assert _doctor_exit_code(diag) == 2
