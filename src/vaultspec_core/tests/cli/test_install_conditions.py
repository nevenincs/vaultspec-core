"""Install/uninstall/provider management: on-disk condition tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import DirName

if TYPE_CHECKING:
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fresh install
# ---------------------------------------------------------------------------


class TestFreshInstall:
    """Verify a clean install scaffolds every expected artifact."""

    def test_install_creates_all_expected_dirs(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore().run("install")

        for dirname in (
            DirName.VAULTSPEC,
            DirName.CLAUDE,
            DirName.GEMINI,
            DirName.ANTIGRAVITY,
            DirName.CODEX,
        ):
            assert (factory.root / dirname).is_dir(), f"{dirname} missing after install"

    def test_install_creates_manifest_with_all_providers(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.create_gitignore().run("install")

        manifest = factory.read_manifest()
        for provider in ("claude", "gemini", "antigravity", "codex"):
            assert provider in manifest.installed, (
                f"{provider} not in manifest.installed"
            )

    def test_install_creates_gitignore_block(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore().run("install")

        assert factory.gitignore_has_block()

    def test_install_creates_mcp_json(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore().run("install")

        assert factory.mcp_has_vaultspec_entry()


# ---------------------------------------------------------------------------
# Install with pre-existing provider dir
# ---------------------------------------------------------------------------


class TestInstallOverExisting:
    """Pre-existing provider directories must survive install."""

    def test_install_over_existing_claude_dir(self, factory: WorkspaceFactory) -> None:
        factory.preset_pre_existing_provider("claude").create_gitignore().run("install")

        # User files must survive
        user_notes = factory.root / DirName.CLAUDE / "my-notes.txt"
        assert user_notes.exists(), "user file was deleted during install"

        # Rules must be synced
        assert factory.provider_has_rules("claude")

    def test_install_over_existing_empty_provider_dir(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.create_bare_provider_dir("claude").create_gitignore().run("install")

        assert factory.provider_has_rules("claude")


# ---------------------------------------------------------------------------
# Install with pre-existing .mcp.json
# ---------------------------------------------------------------------------


class TestInstallMergesMcp:
    """User MCP entries must be preserved when install adds its own."""

    def test_install_merges_into_existing_mcp(self, factory: WorkspaceFactory) -> None:
        factory.create_user_only_mcp().create_gitignore().run("install")

        assert factory.mcp_has_vaultspec_entry(), "vaultspec entry missing"
        assert factory.mcp_has_user_entry("my-server"), "user server was dropped"


# ---------------------------------------------------------------------------
# Install --upgrade
# ---------------------------------------------------------------------------


class TestInstallManifestFields:
    """Install must populate v2 manifest metadata fields."""

    def test_install_populates_v2_manifest_fields(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        manifest = factory.read_manifest()
        assert manifest.vaultspec_version, "vaultspec_version is empty after install"
        assert manifest.installed_at, "installed_at is empty after install"

    def test_install_populates_provider_state(self, factory: WorkspaceFactory) -> None:
        factory.install()
        manifest = factory.read_manifest()
        assert manifest.provider_state, "provider_state is empty after install"
        for provider, state in manifest.provider_state.items():
            assert "installed_at" in state, (
                f"provider_state[{provider}] missing installed_at"
            )


class TestVaultspecAsFile:
    """.vaultspec as a file must block install."""

    def test_vaultspec_as_file_error(self, factory: WorkspaceFactory) -> None:
        factory.vaultspec_as_file()
        result = factory.run("install")
        assert result.exit_code != 0, (
            f"Expected non-zero exit when .vaultspec is a file, got: {result.output}"
        )


class TestInstallUpgrade:
    """--upgrade must refresh versioned content without full re-scaffold."""

    def test_upgrade_on_outdated_install(self, factory: WorkspaceFactory) -> None:
        factory.install().preset_outdated_install()

        old_manifest = factory.read_manifest()
        assert old_manifest.vaultspec_version == "0.0.1"

        factory.run("install", "--upgrade")

        new_manifest = factory.read_manifest()
        assert new_manifest.vaultspec_version != "0.0.1", (
            "version was not updated after --upgrade"
        )

    def test_upgrade_force_re_opts_gitignore(self, factory: WorkspaceFactory) -> None:
        factory.install().remove_gitignore_block()
        assert not factory.gitignore_has_block()

        factory.run("install", "--upgrade", "--force")

        assert factory.gitignore_has_block(), (
            "gitignore block not restored by --upgrade --force"
        )


# ---------------------------------------------------------------------------
# Install --force over corrupted
# ---------------------------------------------------------------------------


class TestInstallForceCorrupted:
    """--force must recover a corrupted workspace."""

    def test_install_force_over_corrupted_workspace(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().corrupt_manifest()
        assert not factory.manifest_is_valid_json()

        factory.run("install", "--force")

        assert factory.manifest_is_valid_json(), "manifest still invalid after --force"
        assert factory.is_installed


# ---------------------------------------------------------------------------
# Upgrade edge cases
# ---------------------------------------------------------------------------


class TestUpgradeEdgeCases:
    """Upgrade edge cases: re-seed builtins, dry-run, non-installed."""

    def test_upgrade_reseeds_builtins(self, factory: WorkspaceFactory) -> None:
        factory.install().delete_builtins()
        # Verify builtins were deleted
        rules_src = factory.path / ".vaultspec" / "rules"
        assert not list(rules_src.glob("*.builtin.md")), (
            "Builtins still exist after delete_builtins"
        )

        factory.run("install", "--upgrade")
        assert list(rules_src.glob("*.builtin.md")), (
            "Builtins were not re-seeded by --upgrade"
        )

    def test_upgrade_dry_run_no_changes(self, factory: WorkspaceFactory) -> None:
        factory.install()
        manifest_before = factory.read_manifest()
        version_before = manifest_before.vaultspec_version

        factory.install(upgrade=True, dry_run=True)
        manifest_after = factory.read_manifest()
        assert manifest_after.vaultspec_version == version_before, (
            "vaultspec_version changed despite dry-run"
        )

    def test_upgrade_on_non_installed_errors(self, factory: WorkspaceFactory) -> None:
        result = factory.run("install", "--upgrade")
        assert result.exit_code != 0, (
            f"Expected non-zero exit for upgrade on non-installed workspace: "
            f"{result.output}"
        )


# ---------------------------------------------------------------------------
# Install --skip
# ---------------------------------------------------------------------------


class TestInstallSkip:
    """--skip must exclude the named component."""

    def test_install_core_scaffolds_framework_only(
        self, factory: WorkspaceFactory
    ) -> None:
        """`install core` scaffolds `.vaultspec/` and zero provider directories.

        Contract: the `core` provider installs the framework directory only
        (`docs/CLI.md`: "core installs `.vaultspec/` only, without any
        provider config"). `init_run` enforces this via
        `_PROVIDER_TO_TOOLS["core"] == []`, so no provider tool is enrolled.

        The post-init `sync_provider` call maps `core` to the `all` sync
        target, but that pass only ever propagates to *enrolled* providers.
        With none enrolled it is a no-op for provider config; on a later
        `install --upgrade core` against an existing install it correctly
        re-propagates the re-seeded builtins to whatever providers are
        already enrolled. This test pins the fresh-install half of that
        contract: no provider directory may appear from `install core`.
        """
        factory.create_gitignore()
        factory.install(provider="core")

        assert (factory.root / ".vaultspec").is_dir(), (
            "`install core` did not scaffold the framework directory"
        )
        for provider in ("claude", "gemini", "antigravity", "codex"):
            assert not factory.provider_dir_exists(provider), (
                f"`install core` created the {provider} provider directory; "
                "core must scaffold the framework only"
            )

    def test_skip_core_installs_provider_only(self, factory: WorkspaceFactory) -> None:
        # Pre-create .vaultspec/ so core scaffold is present
        (factory.root / ".vaultspec" / "rules").mkdir(parents=True, exist_ok=True)
        factory.create_gitignore()
        factory.install(skip={"core"})
        # At least one provider dir should exist
        assert factory.provider_dir_exists("claude") or factory.provider_dir_exists(
            "gemini"
        ), "No provider dirs created when skipping core"

    def test_skip_core_via_cli_does_not_log_sync_failure(
        self, factory: WorkspaceFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Regression: `install --skip core` must not crash `sync_provider`.

        `sync_provider` rejects `core` in its skip set (`allow_core=False`).
        `install_run` previously forwarded the unfiltered skip set, which
        raised `ProviderError`. The error was caught by the post-sync
        `try/except (VaultSpecError, OSError)` block and silently logged
        as a warning, so the headline test only verified provider dirs
        existed.  This test locks the absence of that warning.
        """
        import logging

        # Pre-create .vaultspec/ so core scaffold is present.
        (factory.root / ".vaultspec" / "rules").mkdir(parents=True, exist_ok=True)
        factory.create_gitignore()

        caplog.set_level(logging.WARNING, logger="vaultspec_core.core.commands")
        factory.install(skip={"core"})

        sync_failures = [
            record
            for record in caplog.records
            if "Sync failed during install" in record.getMessage()
        ]
        assert not sync_failures, (
            "`install --skip core` produced sync-failure warnings; "
            "sync_provider must receive a skip set with `core` filtered out: "
            f"{[r.getMessage() for r in sync_failures]}"
        )

    def test_upgrade_without_force_preserves_user_authored_content(
        self, factory: WorkspaceFactory
    ) -> None:
        """Regression: `install --upgrade` (no `--force`) must preserve user files.

        Pre-fix the upgrade path called
        `sync_provider(sync_target, force=True, skip=skip - {"core"})`
        with `force` hardcoded, ignoring the `force=force` parameter
        threaded through `install_run`. That meant
        `vaultspec-core install --upgrade` silently overwrote user-
        authored system prompts and configs (files without the
        vaultspec managed-block marker) every time, breaking the
        documented contract where `--upgrade` and `--force` are
        independent flags.

        This test installs, replaces `.gemini/SYSTEM.md` with content
        lacking the vaultspec marker, then runs `install --upgrade`
        without `force=True`. The user-authored content MUST survive.
        Paired with `test_install_force_propagates_to_sync_provider`,
        these two tests lock the full `--force`/`--upgrade` matrix:
        force=True overwrites, force=False preserves, on both paths.
        """
        factory.install()

        system_file = factory.root / DirName.GEMINI / "SYSTEM.md"
        assert system_file.exists(), (
            "gemini SYSTEM.md must exist after a clean install for this "
            f"regression test to be meaningful (looked at {system_file})"
        )

        # User-authored content without the vaultspec managed-block marker.
        sentinel = (
            "user-authored upgrade-preservation sentinel without vaultspec marker"
        )
        system_file.write_text(sentinel, encoding="utf-8")

        # `--upgrade` without `--force`: sync_provider's force= must be
        # False so user-authored files are skipped (with a warning), not
        # overwritten.
        factory.install(upgrade=True)

        survived = system_file.read_text(encoding="utf-8")
        assert survived == sentinel, (
            "`install --upgrade` (no --force) overwrote user-authored "
            "content. The sync pass is receiving force=True unconditionally "
            "on the upgrade path; user content is not safe across upgrades."
        )

    def test_install_force_propagates_to_sync_provider(
        self, factory: WorkspaceFactory
    ) -> None:
        """Regression: `install --force` must overwrite user-authored system files.

        The fresh-install path used to call
        `sync_provider(sync_target, skip=skip - {"core"})` without
        forwarding `force=force`. `sync_provider`'s `system_sync` pass
        preserves user-authored content (files lacking the vaultspec
        managed-block marker) unless `force=True` is set, so an
        `install --force` invocation would silently leave a
        user-replaced `.gemini/SYSTEM.md` unchanged and only emit a
        skipped-with-warning entry.

        This test replaces `.gemini/SYSTEM.md` with content that does
        NOT carry the vaultspec marker (i.e., looks user-authored),
        re-runs install with `force=True`, and asserts the file was
        overwritten with the canonical scaffold. Without `force=force`
        propagation, the sync pass skips the file and the sentinel
        survives.
        """
        factory.install()

        system_file = factory.root / DirName.GEMINI / "SYSTEM.md"
        assert system_file.exists(), (
            "gemini SYSTEM.md must exist after a clean install for this "
            f"regression test to be meaningful (looked at {system_file})"
        )

        # Write user-authored content with NO vaultspec marker so the
        # sync pass treats it as user-owned and only overwrites under
        # force.
        sentinel = "user-authored sentinel without vaultspec marker"
        system_file.write_text(sentinel, encoding="utf-8")

        factory.install(force=True)

        restored = system_file.read_text(encoding="utf-8")
        assert sentinel not in restored, (
            "`install --force` did not overwrite the user-authored "
            "`.gemini/SYSTEM.md`. The sync pass is not receiving "
            "`force=force`; user-authored content survives a forced "
            "install."
        )

    def test_skip_provider_installs_others(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore()
        result = factory.run("install", "--skip", "claude")
        assert result.exit_code == 0, result.output
        assert factory.provider_dir_exists("gemini"), (
            "gemini not installed when skipping claude"
        )
        assert not factory.provider_dir_exists("claude"), (
            "claude was installed despite --skip claude"
        )


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


class TestUninstall:
    """Uninstall must tear down managed artifacts cleanly."""

    def test_uninstall_removes_all_dirs(self, factory: WorkspaceFactory) -> None:
        factory.install().run("uninstall", "--force")

        assert not factory.is_installed
        for provider in ("claude", "gemini", "antigravity", "codex"):
            assert not factory.provider_dir_exists(provider), (
                f"{provider} dir still exists"
            )

    def test_uninstall_preserves_vault_by_default(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        vault = factory.root / DirName.VAULT
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "dummy.md").write_text("keep me", encoding="utf-8")

        factory.run("uninstall", "--force")

        assert vault.is_dir(), ".vault/ was removed without --remove-vault"

    def test_uninstall_removes_vault_with_flag(self, factory: WorkspaceFactory) -> None:
        factory.install()
        vault = factory.root / DirName.VAULT
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "dummy.md").write_text("keep me", encoding="utf-8")

        factory.run("uninstall", "--remove-vault", "--force")

        assert not vault.exists(), ".vault/ survived --remove-vault"


# ---------------------------------------------------------------------------
# Uninstall preserves user MCP entries
# ---------------------------------------------------------------------------


class TestUninstallPreservesMcp:
    """Uninstall must leave user-defined MCP servers untouched."""

    def test_uninstall_preserves_user_mcp_entries(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().add_user_mcp_servers().run("uninstall", "--force")

        assert not factory.mcp_has_vaultspec_entry(), (
            "vaultspec entry survived uninstall"
        )
        assert factory.mcp_has_user_entry("my-custom-server"), (
            "user MCP entry was deleted"
        )


# ---------------------------------------------------------------------------
# Uninstall removes gitignore block
# ---------------------------------------------------------------------------


class TestUninstallGitignore:
    """Uninstall must clean up the managed gitignore block when vault is removed."""

    def test_uninstall_preserves_gitignore_block_when_vault_kept(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().run("uninstall", "--force")

        # Gitignore block is preserved when .vault/ is kept (default)
        assert factory.gitignore_has_block()

    def test_uninstall_removes_gitignore_block_with_remove_vault(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().run("uninstall", "--remove-vault", "--force")

        assert not factory.gitignore_has_block()


# ---------------------------------------------------------------------------
# Single provider install/uninstall
# ---------------------------------------------------------------------------


class TestSingleProvider:
    """Operations scoped to a single provider name."""

    def test_install_single_provider(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore().run("install", "claude")

        assert factory.provider_dir_exists("claude")
        assert not factory.provider_dir_exists("gemini"), (
            "gemini installed despite single-provider request"
        )

    def test_uninstall_single_provider(self, factory: WorkspaceFactory) -> None:
        factory.install().run("uninstall", "claude", "--force")

        assert not factory.provider_dir_exists("claude"), (
            "claude dir survived uninstall"
        )
        assert factory.provider_dir_exists("gemini"), (
            "gemini was removed by single-provider uninstall"
        )


# ---------------------------------------------------------------------------
# Adding provider to existing repo
# ---------------------------------------------------------------------------


class TestAddProvider:
    """Adding a second provider to an existing installation."""

    def test_add_provider_to_existing_install(self, factory: WorkspaceFactory) -> None:
        factory.install(provider="claude").run("install", "gemini", "--force")

        manifest = factory.read_manifest()
        assert "claude" in manifest.installed
        assert "gemini" in manifest.installed


# ---------------------------------------------------------------------------
# Removing nonexistent provider
# ---------------------------------------------------------------------------


class TestRemoveNonexistent:
    """Double-uninstall must not crash."""

    def test_uninstall_nonexistent_provider(self, factory: WorkspaceFactory) -> None:
        factory.install().run("uninstall", "claude", "--force")

        # Second removal of the same provider should exit cleanly
        result = factory.run("uninstall", "claude", "--force")
        assert result.exit_code == 0, (
            f"double uninstall failed with code {result.exit_code}: {result.output}"
        )


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Uninstall single provider
# ---------------------------------------------------------------------------


class TestUninstallSingleProvider:
    """Per-provider uninstall must update manifest and preserve shared dirs."""

    def test_uninstall_single_provider_updates_manifest(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        result = factory.run("uninstall", "claude", "--force")
        assert result.exit_code == 0, result.output

        manifest = factory.read_manifest()
        assert "claude" not in manifest.installed, (
            "claude still in manifest after uninstall"
        )

    def test_uninstall_preserves_shared_agents_dir(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install()
        result = factory.run("uninstall", "gemini", "--force")
        assert result.exit_code == 0, result.output

        # .agents/ is used by antigravity and must survive gemini removal
        agents_dir = factory.path / ".agents"
        assert agents_dir.is_dir(), ".agents/ was removed by gemini uninstall"

    def test_uninstall_force_removes_dir_with_user_content(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().add_user_content("claude")
        result = factory.run("uninstall", "claude", "--force")
        assert result.exit_code == 0, result.output
        assert not factory.provider_dir_exists("claude"), (
            ".claude/ survived --force uninstall despite user content"
        )


# ---------------------------------------------------------------------------
# Uninstall --dry-run
# ---------------------------------------------------------------------------


class TestUninstallDryRun:
    """--dry-run must not actually remove anything."""

    def test_uninstall_dry_run_no_changes(self, factory: WorkspaceFactory) -> None:
        factory.install()
        result = factory.run("uninstall", "--dry-run", "--force")
        assert result.exit_code == 0, result.output

        # Everything should still exist
        assert factory.is_installed, ".vaultspec/ removed despite --dry-run"
        for provider in ("claude", "gemini", "antigravity", "codex"):
            assert factory.provider_dir_exists(provider), (
                f"{provider} dir removed despite --dry-run"
            )


# ---------------------------------------------------------------------------
# Uninstall with corrupted manifest
# ---------------------------------------------------------------------------


class TestUninstallCorruptedManifest:
    """Uninstall behaviour when manifest is unparseable."""

    def test_uninstall_corrupted_manifest_force_proceeds(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().corrupt_manifest()
        result = factory.run("uninstall", "--force")
        assert result.exit_code == 0, result.output

        # Provider dirs should be removed
        for provider in ("claude", "gemini"):
            assert not factory.provider_dir_exists(provider), (
                f"{provider} dir survived --force uninstall with corrupted manifest"
            )

    def test_uninstall_corrupted_manifest_no_force_blocked(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().corrupt_manifest()
        result = factory.run("uninstall")
        assert result.exit_code != 0, (
            f"Expected non-zero exit for uninstall with corrupted manifest "
            f"without --force: {result.output}"
        )


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Install -> uninstall -> reinstall must yield a clean workspace."""

    def test_install_uninstall_reinstall_cycle(self, factory: WorkspaceFactory) -> None:
        factory.install().run("uninstall", "--force")
        assert not factory.is_installed

        factory.run("install")
        assert factory.is_installed
        assert factory.manifest_is_valid_json()
        for provider in ("claude", "gemini", "antigravity", "codex"):
            assert factory.provider_dir_exists(provider)


# ---------------------------------------------------------------------------
# Install --skip mcp
# ---------------------------------------------------------------------------


class TestInstallSkipMcp:
    """--skip mcp must prevent MCP scaffolding."""

    def test_skip_mcp_prevents_mcp_json_creation(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.create_gitignore()
        result = factory.run("install", "--skip", "mcp")
        assert result.exit_code == 0, result.output
        assert not factory.mcp_has_vaultspec_entry(), (
            ".mcp.json vaultspec entry created despite --skip mcp"
        )

    def test_skip_mcp_still_installs_providers(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore()
        result = factory.run("install", "--skip", "mcp")
        assert result.exit_code == 0, result.output
        assert factory.provider_dir_exists("claude"), (
            "claude dir missing when --skip mcp"
        )

    def test_skip_mcp_dry_run_excludes_mcp(self, factory: WorkspaceFactory) -> None:
        factory.create_gitignore()
        result = factory.run("install", "--skip", "mcp", "--dry-run")
        assert result.exit_code == 0, result.output
        assert not factory.mcp_has_vaultspec_entry(), (
            ".mcp.json should not exist after --skip mcp --dry-run"
        )


# ---------------------------------------------------------------------------
# Sync repairs missing MCP entry
# ---------------------------------------------------------------------------


class TestSyncRepairsMcp:
    """Sync must repair a missing MCP entry."""

    def test_sync_repairs_deleted_mcp_json(self, factory: WorkspaceFactory) -> None:
        factory.install().delete_mcp_json()
        assert not (factory.root / ".mcp.json").exists()

        factory.sync()

        assert factory.mcp_has_vaultspec_entry(), (
            "sync did not repair missing .mcp.json"
        )

    def test_sync_repairs_missing_vaultspec_entry(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().remove_mcp_vaultspec_entry()
        assert not factory.mcp_has_vaultspec_entry()

        factory.sync()

        assert factory.mcp_has_vaultspec_entry(), (
            "sync did not repair missing vaultspec-core entry"
        )

    def test_sync_preserves_user_entries_on_repair(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().add_user_mcp_servers().remove_mcp_vaultspec_entry()

        factory.sync()

        assert factory.mcp_has_vaultspec_entry(), "vaultspec entry not repaired"
        assert factory.mcp_has_user_entry("my-custom-server"), (
            "user entry lost during MCP repair"
        )


# ---------------------------------------------------------------------------
# Upgrade re-scaffolds MCP
# ---------------------------------------------------------------------------


class TestUpgradeRepairsMcp:
    """--upgrade must repair a missing MCP entry."""

    def test_upgrade_repairs_deleted_mcp_json(self, factory: WorkspaceFactory) -> None:
        factory.install().delete_mcp_json()
        assert not (factory.root / ".mcp.json").exists()

        factory.run("install", "--upgrade")

        assert factory.mcp_has_vaultspec_entry(), (
            "--upgrade did not repair missing .mcp.json"
        )

    def test_upgrade_repairs_missing_vaultspec_entry(
        self, factory: WorkspaceFactory
    ) -> None:
        factory.install().remove_mcp_vaultspec_entry()
        assert not factory.mcp_has_vaultspec_entry()

        factory.run("install", "--upgrade")

        assert factory.mcp_has_vaultspec_entry(), (
            "--upgrade did not repair missing vaultspec-core entry"
        )
