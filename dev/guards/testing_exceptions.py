"""Reviewed test mechanisms that require isolated state or fault injection.

Entries name exact scopes and mechanisms. New tests remain subject to the default
ban; removing an exception's last use fails the guard until the entry is removed.
Production boundaries must never be disabled merely to make a test pass.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestMechanismException:
    path: str
    scopes: tuple[str, ...]
    mechanisms: frozenset[str]
    reason: str


EXCEPTIONS = (
    TestMechanismException(
        "dev/packaging/tests/test_published_surface.py",
        ("<module>",),
        frozenset({"unittest.mock"}),
        "Import used only by the release-verification cases listed below.",
    ),
    TestMechanismException(
        "dev/packaging/tests/test_published_surface.py",
        (
            "release_files",
            "test_bad_checksums_never_reach_verifier_or_execution",
            "test_rejected_provenance_never_executes_the_wheel",
            "test_unavailable_verifier_never_executes_the_wheel",
            "test_verified_bytes_execute_only_after_full_identity_verification",
            "test_conflicting_checksum_spellings_never_reach_execution",
            "test_container_receives_only_readonly_wheel_and_no_host_credentials",
            "test_recording_collected_data_does_not_download_or_execute_release_code",
            "test_recording_refuses_data_for_a_superseded_release",
            "test_release_commit_resolution_requires_a_full_commit_digest",
        ),
        frozenset({"monkeypatch", "Mock"}),
        "Inject release/verifier failures and record subprocess calls so rejected "
        "release bytes cannot execute; test the production verification policy.",
    ),
    TestMechanismException(
        "src/vaultspec_core/config/tests/test_managed_roots.py",
        ("isolated_state", "test_cached_custom_config_rechecks_roots"),
        frozenset({"monkeypatch"}),
        "Isolate the workspace ContextVar and the configured docs environment.",
    ),
    TestMechanismException(
        "src/vaultspec_core/config/tests/test_managed_roots.py",
        ("_link", "test_resolution_rejects_windows_junctions"),
        frozenset({"pytest.skip"}),
        "Skip only when the OS lacks the link capability being exercised.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_corpus_security.py",
        ("test_corpus_consumers_prune_redirected_directories",),
        frozenset({"pytest.skip"}),
        "The junction variant requires Windows; symlink variants still run.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_corpus_security.py",
        ("test_reader_rejects_replacement_between_validation_and_open",),
        frozenset({"monkeypatch"}),
        "Replace a real file at the validation/open transition to prove the "
        "descriptor-identity guard rejects it.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_corpus_security.py",
        (
            "test_explicit_external_docs_root_remains_usable_and_rejects_links",
            "test_reader_preserves_bytes_and_newlines_with_custom_docs_and_aliases",
        ),
        frozenset({"monkeypatch"}),
        "Set the configured docs environment while exercising real files.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_mcps.py",
        ("test_repository_cannot_forge_mcp_ownership",),
        frozenset({"monkeypatch"}),
        "Point operator-home authority at a private test directory.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_mcps_trust.py",
        ("workspace",),
        frozenset({"monkeypatch"}),
        "Isolate operator home and workspace discovery from the developer's state.",
    ),
    TestMechanismException(
        "src/vaultspec_core/core/tests/test_mcps_trust.py",
        ("test_grant_snapshot_not_later_bytes",),
        frozenset({"monkeypatch"}),
        "Change real definition bytes during rendering to challenge grant binding.",
    ),
    TestMechanismException(
        "src/vaultspec_core/mcp_server/tests/test_catalog_injection.py",
        ("test_poisoned_inventory_rejected_before_spawn",),
        frozenset({"monkeypatch"}),
        "A spawn witness proves poisoned catalog entries never launch a child.",
    ),
    TestMechanismException(
        "src/vaultspec_core/mcp_server/tests/test_corpus_symlinks.py",
        ("test_find_never_returns_linked_content_or_resource_uri",),
        frozenset({"monkeypatch"}),
        "Replace a real document immediately after listing to challenge revalidation.",
    ),
    TestMechanismException(
        "src/vaultspec_core/mcp_server/tests/test_gateway_import_security.py",
        (
            "test_invoke_ignores_shadow_packages",
            "test_gateway_environment_removes_python_import_overrides",
            "test_invoke_preserves_relative_cli_paths",
        ),
        frozenset({"monkeypatch"}),
        "Change cwd and import-related environment; every gateway child is real.",
    ),
    TestMechanismException(
        "src/vaultspec_core/mcp_server/tests/test_plan_target_boundary.py",
        ("test_linked_targets_cannot_escape_plan_directory",),
        frozenset({"pytest.mark.skipif"}),
        "Only the Windows junction parameters are skipped on other platforms.",
    ),
    TestMechanismException(
        "src/vaultspec_core/mcp_server/tests/test_reference_maintenance_denial.py",
        ("test_gateway_refuses_maintenance_before_spawn",),
        frozenset({"monkeypatch"}),
        "A spawn witness proves blocked maintenance verbs never launch a child.",
    ),
    TestMechanismException(
        "src/vaultspec_core/migrations/tests/test_managed_directory_links.py",
        ("test_windows_junction_is_rejected",),
        frozenset({"pytest.mark.skipif"}),
        "Junction creation is available only on Windows.",
    ),
    TestMechanismException(
        "src/vaultspec_core/migrations/tests/test_mcp_ownership.py",
        ("test_rejects_repository_links",),
        frozenset({"pytest.skip"}),
        "Skip only when the host cannot create the filesystem link under test.",
    ),
    TestMechanismException(
        "src/vaultspec_core/tests/cli/test_cli_reference_surface.py",
        ("test_trusted_snapshot_record_writes_a_new_surface",),
        frozenset({"monkeypatch"}),
        "Remove the inherited gateway marker for the explicitly trusted CLI control.",
    ),
    TestMechanismException(
        "src/vaultspec_core/tests/cli/test_mcp_consent.py",
        (
            "test_terminal_confirmation_is_required",
            "test_file_changed_while_operator_reviews_is_not_approved",
            "test_repository_warnings_cannot_erase_approval_display",
            "test_split_source_approval_matches_top_level_sync",
        ),
        frozenset({"monkeypatch"}),
        "Model TTY/confirmation state and a definition changing while the operator "
        "reviews it; grants and enrollment use the real production ledger.",
    ),
    TestMechanismException(
        "src/vaultspec_core/vaultcore/tests/test_query_archive_security.py",
        ("_link",),
        frozenset({"pytest.skip"}),
        "Only the Windows junction variant is skipped on other platforms.",
    ),
    TestMechanismException(
        "src/vaultspec_core/vaultcore/tests/test_query_archive_security.py",
        ("test_rejects_linked_configured_vault_ancestors_inside_project",),
        frozenset({"monkeypatch"}),
        "Set the docs-root environment while testing real redirected ancestors.",
    ),
)
