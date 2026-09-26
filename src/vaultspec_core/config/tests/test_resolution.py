"""One resolution order, one vocabulary, one refusal, for every package.

The contract another package imports: the word tables, blank as unset, the
chain from a package-scoped name to the framework name behind it, the
refusal that names the variable an operator actually set, and the workspace
``.env`` gate opening on the mode of the package that owns the credential.

Every environment here is an explicit mapping and every workspace a real
directory, because what is under test is precisely how the code reads the
world it is given.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import (
    CONFIG_REGISTRY,
    PACKAGE,
    VAULTSPEC_CORE_TYPESAFE_API_KEY,
    VAULTSPEC_LOG_LEVEL,
    VAULTSPEC_STDIO_WATCHDOG,
    VAULTSPEC_TARGET_DIR,
    ConfigVariable,
    Credential,
    CredentialSource,
    VariableScope,
    VaultSpecConfig,
    check_environment,
    env_flag,
    env_source,
    env_value,
    is_unattended,
    register_registry,
    resolve_credential,
    unattended_declared,
)
from vaultspec_core.config.config import forget_registry_for_tests
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.exceptions import ConfigurationError
from vaultspec_core.core.workspace_mode import (
    PackageDeclaration,
    write_package_declaration,
)
from vaultspec_core.env_values import (
    BOOL_SHAPE,
    FALSE_TOKENS,
    TRUE_TOKENS,
    is_blank,
    parse_bool,
    rejection,
)
from vaultspec_core.logging_config import LOG_LEVELS, resolve_log_level

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: A companion package, declared here exactly as a real one would declare
#: itself: its own entries, chained to the framework names core owns.
COMPANION = "vaultspec-resolution-companion"

#: The framework rungs the companion's own names fall back to. They are core's
#: real entries, because a fallback may name nothing else.
FRAMEWORK_ROOT = VAULTSPEC_TARGET_DIR
FRAMEWORK_SWITCH = VAULTSPEC_STDIO_WATCHDOG

COMPANION_ROOT = ConfigVariable(
    env_name="VAULTSPEC_RESOLUTION_COMPANION_ROOT",
    attr_name=None,
    var_type=str,
    default=None,
    description="The companion's own root, chained to the framework name.",
    fallback=FRAMEWORK_ROOT,
)

COMPANION_SWITCH = ConfigVariable(
    env_name="VAULTSPEC_RESOLUTION_COMPANION_SWITCH",
    attr_name=None,
    var_type=str,
    default=None,
    description="The companion's own switch, chained to the framework name.",
    fallback=FRAMEWORK_SWITCH,
)

COMPANION_KEY = ConfigVariable(
    env_name="VAULTSPEC_RESOLUTION_COMPANION_API_KEY",
    attr_name=None,
    var_type=str,
    default=None,
    description="The companion's credential, eligible for a workspace .env.",
    secret=True,
    workspace_dotenv=True,
)

COMPANION_DOTENV_KEY = "companion-dotenv-4f81a26c9b03"


@pytest.fixture(autouse=True, scope="module")
def _companion_registry() -> Iterator[None]:
    """Declare the companion for this module only.

    A package registers at import and never withdraws, but a package invented
    by a test must not outlive it: the registries are process-global, and an
    entry left behind is state no code under test put there.
    """
    register_registry(COMPANION, [COMPANION_ROOT, COMPANION_SWITCH, COMPANION_KEY])
    yield
    forget_registry_for_tests(COMPANION)


def _unregistered(
    env_name: str = "VAULTSPEC_RESOLUTION_UNDECLARED",
    *,
    secret: bool = False,
    scope: VariableScope = VariableScope.PRODUCT,
    fallback: ConfigVariable | None = None,
) -> ConfigVariable:
    """An entry built outside any registry, for the refusal paths."""
    return ConfigVariable(
        env_name=env_name,
        attr_name=None,
        var_type=str,
        default=None,
        description="Declared outside any registry.",
        secret=secret,
        scope=scope,
        fallback=fallback,
    )


class TestVocabulary:
    def test_the_tables_are_the_agreed_words(self) -> None:
        assert sorted(TRUE_TOKENS) == ["1", "on", "true", "yes"]
        assert sorted(FALSE_TOKENS) == ["0", "false", "no", "off"]

    def test_no_word_means_both(self) -> None:
        assert sorted(TRUE_TOKENS & FALSE_TOKENS) == []

    def test_the_shape_names_every_accepted_word(self) -> None:
        assert BOOL_SHAPE == "one of 0, 1, false, no, off, on, true, yes"

    @pytest.mark.parametrize("word", sorted(TRUE_TOKENS))
    def test_every_true_word_parses_true(self, word: str) -> None:
        assert parse_bool(word) is True
        assert parse_bool(f"  {word.upper()}  ") is True

    @pytest.mark.parametrize("word", sorted(FALSE_TOKENS))
    def test_every_false_word_parses_false(self, word: str) -> None:
        assert parse_bool(word) is False
        assert parse_bool(f"  {word.upper()}  ") is False

    @pytest.mark.parametrize("word", ["", "   ", "maybe", "2", "enabled", "y"])
    def test_anything_else_parses_to_nothing(self, word: str) -> None:
        assert parse_bool(word) is None

    @pytest.mark.parametrize("raw", [None, "", " ", "\t\n"])
    def test_unset_and_whitespace_are_blank(self, raw: str | None) -> None:
        assert is_blank(raw) is True

    @pytest.mark.parametrize("raw", ["0", "false", " x ", "-"])
    def test_anything_with_a_character_is_not_blank(self, raw: str) -> None:
        assert is_blank(raw) is False


class TestRejectionMessage:
    def test_it_names_the_variable_the_value_and_the_shape(self) -> None:
        error = rejection("VAULTSPEC_EXAMPLE", BOOL_SHAPE, "maybe")

        assert str(error) == (
            "VAULTSPEC_EXAMPLE must be one of "
            "0, 1, false, no, off, on, true, yes, got 'maybe'"
        )

    def test_a_secret_is_named_but_never_quoted(self) -> None:
        secret = "sk-resolution-6d2f0a8e1c74"

        error = rejection("VAULTSPEC_EXAMPLE_KEY", "a key", secret, secret=True)

        assert "VAULTSPEC_EXAMPLE_KEY" in str(error)
        assert "<redacted>" in str(error)
        assert secret not in str(error)


class TestBlankIsUnset:
    @pytest.mark.parametrize("raw", ["", "   "])
    def test_a_blank_value_supplies_nothing(self, raw: str) -> None:
        environ = {FRAMEWORK_ROOT.env_name: raw}

        assert env_value(FRAMEWORK_ROOT, environ) is None
        assert env_source(FRAMEWORK_ROOT, environ) is None
        assert env_flag(FRAMEWORK_SWITCH, {FRAMEWORK_SWITCH.env_name: raw}) is None

    def test_surrounding_whitespace_is_not_part_of_the_value(self) -> None:
        environ = {FRAMEWORK_ROOT.env_name: "  /srv/project  "}

        assert env_value(FRAMEWORK_ROOT, environ) == "/srv/project"


class TestChainFallback:
    def test_the_framework_name_answers_when_the_package_name_is_unset(self) -> None:
        environ = {FRAMEWORK_ROOT.env_name: "/srv/framework"}

        assert env_value(COMPANION_ROOT, environ) == "/srv/framework"
        assert env_source(COMPANION_ROOT, environ) is FRAMEWORK_ROOT

    def test_the_package_name_wins_when_both_are_set(self) -> None:
        environ = {
            COMPANION_ROOT.env_name: "/srv/companion",
            FRAMEWORK_ROOT.env_name: "/srv/framework",
        }

        assert env_value(COMPANION_ROOT, environ) == "/srv/companion"
        assert env_source(COMPANION_ROOT, environ) is COMPANION_ROOT

    def test_a_blank_package_name_falls_through_to_the_framework_name(self) -> None:
        environ = {
            COMPANION_ROOT.env_name: "   ",
            FRAMEWORK_ROOT.env_name: "/srv/framework",
        }

        assert env_value(COMPANION_ROOT, environ) == "/srv/framework"
        assert env_source(COMPANION_ROOT, environ) is FRAMEWORK_ROOT

    def test_neither_set_supplies_nothing(self) -> None:
        assert env_value(COMPANION_ROOT, {}) is None
        assert env_source(COMPANION_ROOT, {}) is None

    def test_a_flag_follows_the_same_chain(self) -> None:
        assert env_flag(COMPANION_SWITCH, {FRAMEWORK_SWITCH.env_name: "on"}) is True
        assert (
            env_flag(
                COMPANION_SWITCH,
                {
                    COMPANION_SWITCH.env_name: "off",
                    FRAMEWORK_SWITCH.env_name: "on",
                },
            )
            is False
        )

    def test_a_credential_never_chains(self) -> None:
        with pytest.raises(ValueError, match="never chains"):
            _unregistered(secret=True, fallback=FRAMEWORK_ROOT)

    def test_nothing_chains_to_a_credential(self) -> None:
        with pytest.raises(ValueError, match="never chains"):
            _unregistered(fallback=COMPANION_KEY)

    def test_an_external_convention_declares_no_fallback(self) -> None:
        with pytest.raises(ValueError, match="external convention"):
            _unregistered(
                "RESOLUTION_BORROWED",
                scope=VariableScope.EXTERNAL,
                fallback=FRAMEWORK_ROOT,
            )


class TestFlagRejection:
    def test_an_unrecognised_word_is_refused(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            env_flag(FRAMEWORK_SWITCH, {FRAMEWORK_SWITCH.env_name: "maybe"})

        assert str(refusal.value) == (
            f"{FRAMEWORK_SWITCH.env_name} must be {BOOL_SHAPE}, got 'maybe'"
        )

    def test_the_refusal_names_the_variable_the_operator_set(self) -> None:
        # The chain's head is fine; the framework name behind it is not, and
        # it is the one the operator has to go and fix.
        with pytest.raises(ConfigurationError) as refusal:
            env_flag(COMPANION_SWITCH, {FRAMEWORK_SWITCH.env_name: "sure"})

        assert FRAMEWORK_SWITCH.env_name in str(refusal.value)
        assert COMPANION_SWITCH.env_name not in str(refusal.value)

    def test_the_refusal_names_the_package_variable_when_that_is_the_one_set(
        self,
    ) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            env_flag(
                COMPANION_SWITCH,
                {
                    COMPANION_SWITCH.env_name: "sure",
                    FRAMEWORK_SWITCH.env_name: "on",
                },
            )

        assert COMPANION_SWITCH.env_name in str(refusal.value)

    def test_a_refusal_is_a_domain_error_the_surfaces_already_render(self) -> None:
        from vaultspec_core.core.exceptions import VaultSpecError

        assert issubclass(ConfigurationError, VaultSpecError)


class TestRegistration:
    def test_core_declares_its_own_entries(self) -> None:
        assert PACKAGE == "vaultspec-core"
        assert {var.package for var in CONFIG_REGISTRY} == {PACKAGE}

    def test_a_companion_entry_carries_its_own_package(self) -> None:
        assert COMPANION_ROOT.package == COMPANION
        assert COMPANION_KEY.package == COMPANION

    def test_registering_the_same_entries_again_is_a_no_op(self) -> None:
        register_registry(COMPANION, [COMPANION_ROOT])

        assert COMPANION_ROOT.package == COMPANION
        assert env_value(COMPANION_ROOT, {COMPANION_ROOT.env_name: "x"}) == "x"

    def test_an_entry_cannot_be_declared_by_two_packages(self) -> None:
        with pytest.raises(ValueError, match="already declared by"):
            register_registry("vaultspec-resolution-interloper", [COMPANION_ROOT])

    def test_core_cannot_adopt_a_companion_entry(self) -> None:
        with pytest.raises(ValueError, match="already declared by"):
            register_registry(PACKAGE, [COMPANION_KEY])

    def test_a_name_another_package_declared_cannot_be_redeclared(self) -> None:
        # Identity is not the boundary a credential needs: an interloper that
        # built its own entry under core's key name would otherwise read that
        # key from a workspace .env under its own install mode.
        impostor = ConfigVariable(
            env_name=VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name,
            attr_name=None,
            var_type=str,
            default=None,
            description="Core's credential name, claimed by someone else.",
            secret=True,
            workspace_dotenv=True,
        )

        with pytest.raises(ValueError, match="already declared by"):
            register_registry("vaultspec-resolution-interloper", [impostor])

    def test_a_fallback_into_another_package_is_refused(self) -> None:
        borrower = ConfigVariable(
            env_name="VAULTSPEC_RESOLUTION_BORROWER_ROOT",
            attr_name=None,
            var_type=str,
            default=None,
            description="A third package chaining to the companion's name.",
            fallback=COMPANION_ROOT,
        )

        with pytest.raises(ValueError, match=f"a fallback names a {PACKAGE} variable"):
            register_registry("vaultspec-resolution-borrower", [borrower])

    def test_a_fallback_outside_every_registry_is_refused(self) -> None:
        stray = _unregistered()
        chained = _unregistered("VAULTSPEC_RESOLUTION_CHAINED", fallback=stray)

        with pytest.raises(ValueError, match="which no registry declares"):
            register_registry("vaultspec-resolution-chainer", [chained])

    def test_an_entry_outside_every_registry_is_refused_by_the_accessors(self) -> None:
        stray = _unregistered()

        with pytest.raises(ValueError, match="not declared in a registry"):
            env_value(stray, {stray.env_name: "x"})


#: A typed credential, so that an unusable value is a parse failure the
#: loader has to report. Core's own secret takes any text, so nothing it
#: carries could exercise the redaction the message owes a credential.
_NUMERIC_SECRET = ConfigVariable(
    env_name="VAULTSPEC_RESOLUTION_NUMERIC_SECRET",
    attr_name="typesafe_api_key",
    var_type=int,
    default=None,
    description="A numeric credential, so a bad value is a parse failure.",
    secret=True,
)


@pytest.fixture
def numeric_secret_entry() -> Iterator[None]:
    """Load-bearing for one test: a typed credential core's loader reads."""
    CONFIG_REGISTRY.append(_NUMERIC_SECRET)
    register_registry(PACKAGE, [_NUMERIC_SECRET])
    yield
    forget_registry_for_tests(PACKAGE, [_NUMERIC_SECRET])
    CONFIG_REGISTRY.remove(_NUMERIC_SECRET)


class TestCollectiveRejection:
    def test_one_problem_reports_itself(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            VaultSpecConfig.from_environment(
                environ={"VAULTSPEC_IO_BUFFER_SIZE": "plenty"}
            )

        assert str(refusal.value) == (
            "VAULTSPEC_IO_BUFFER_SIZE must be a whole number, got 'plenty'"
        )

    def test_every_problem_is_reported_together(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            VaultSpecConfig.from_environment(
                environ={
                    "VAULTSPEC_IO_BUFFER_SIZE": "0",
                    "VAULTSPEC_TERMINAL_OUTPUT_LIMIT": "lots",
                    "VAULTSPEC_LOCK_TIMEOUT_SECONDS": "-1",
                }
            )

        assert str(refusal.value) == (
            "3 unusable settings:\n"
            "  - VAULTSPEC_IO_BUFFER_SIZE must be at least 1, got 0\n"
            "  - VAULTSPEC_TERMINAL_OUTPUT_LIMIT must be a whole number, got 'lots'\n"
            "  - VAULTSPEC_LOCK_TIMEOUT_SECONDS must be at least 0.0, got -1.0"
        )

    def test_a_blank_value_leaves_the_default_standing(self) -> None:
        config = VaultSpecConfig.from_environment(
            environ={"VAULTSPEC_IO_BUFFER_SIZE": "   ", "VAULTSPEC_DOCS_DIR": ""}
        )

        assert config.io_buffer_size == 8192
        assert config.docs_dir == VaultSpecConfig().docs_dir

    def test_a_usable_value_is_taken(self) -> None:
        config = VaultSpecConfig.from_environment(
            environ={"VAULTSPEC_IO_BUFFER_SIZE": " 4096 "}
        )

        assert config.io_buffer_size == 4096

    def test_an_override_outranks_the_environment(self) -> None:
        config = VaultSpecConfig.from_environment(
            overrides={"io_buffer_size": 512},
            environ={"VAULTSPEC_IO_BUFFER_SIZE": "4096"},
        )

        assert config.io_buffer_size == 512

    def test_an_override_is_taken_even_where_the_environment_is_unusable(self) -> None:
        # The override is the higher rung, so the variable it displaces is not
        # a problem anybody has to fix first.
        config = VaultSpecConfig.from_environment(
            overrides={"io_buffer_size": 512},
            environ={"VAULTSPEC_IO_BUFFER_SIZE": "0"},
        )

        assert config.io_buffer_size == 512

    @pytest.mark.usefixtures("numeric_secret_entry")
    def test_a_rejected_secret_is_named_but_never_quoted(self) -> None:
        secret = "sk-resolution-b3917e5d0a26"

        with pytest.raises(ConfigurationError) as refusal:
            VaultSpecConfig.from_environment(environ={_NUMERIC_SECRET.env_name: secret})

        reported = str(refusal.value)
        assert _NUMERIC_SECRET.env_name in reported
        assert "<redacted>" in reported
        assert secret not in reported


def _workspace(root: Path, *, package: str | None, mode: InstallMode) -> Path:
    """A real workspace declaring *mode* for *package*, and nothing for others."""
    root.mkdir(parents=True, exist_ok=True)
    if package is not None:
        write_package_declaration(root, package, PackageDeclaration(install_mode=mode))
    return root


def _dotenv(root: Path, value: str = COMPANION_DOTENV_KEY) -> Path:
    (root / ".env").write_text(
        f"# companion credentials\n{COMPANION_KEY.env_name}={value}\n",
        encoding="utf-8",
    )
    return root


class TestPerPackageCredentialGate:
    def test_the_owning_packages_mode_opens_the_file(self, tmp_path: Path) -> None:
        root = _dotenv(
            _workspace(tmp_path, package=COMPANION, mode=InstallMode.DEPENDENCY)
        )

        credential = resolve_credential(
            COMPANION_KEY, root, {}, interpreter_prefix=root / ".venv"
        )

        assert credential == Credential(COMPANION_DOTENV_KEY, CredentialSource.DOTENV)

    def test_another_packages_mode_does_not_open_the_file(self, tmp_path: Path) -> None:
        # The workspace runs core as a dependency and has said nothing about
        # the companion, so the companion's key stays unread.
        root = _dotenv(_workspace(tmp_path, package=PACKAGE, mode=InstallMode.DEV))

        assert (
            resolve_credential(
                COMPANION_KEY, root, {}, interpreter_prefix=root / ".venv"
            )
            is None
        )

    def test_core_is_unaffected_by_a_companions_declaration(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(tmp_path, package=COMPANION, mode=InstallMode.DEV)
        (root / ".env").write_text(
            f"{VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name}=ts-resolution-8c12\n",
            encoding="utf-8",
        )

        assert (
            resolve_credential(
                VAULTSPEC_CORE_TYPESAFE_API_KEY,
                root,
                {},
                interpreter_prefix=root / ".venv",
            )
            is None
        )

    def test_tool_mode_keeps_the_file_closed(self, tmp_path: Path) -> None:
        root = _dotenv(_workspace(tmp_path, package=COMPANION, mode=InstallMode.TOOL))

        assert (
            resolve_credential(
                COMPANION_KEY, root, {}, interpreter_prefix=root / ".venv"
            )
            is None
        )

    def test_an_interpreter_outside_the_workspace_keeps_the_file_closed(
        self, tmp_path: Path
    ) -> None:
        root = _dotenv(
            _workspace(tmp_path / "clone", package=COMPANION, mode=InstallMode.DEV)
        )
        global_tool = tmp_path / "tools" / "companion"

        assert (
            resolve_credential(COMPANION_KEY, root, {}, interpreter_prefix=global_tool)
            is None
        )

    def test_the_environment_is_read_whatever_the_workspace_says(
        self, tmp_path: Path
    ) -> None:
        root = _dotenv(_workspace(tmp_path, package=PACKAGE, mode=InstallMode.TOOL))
        supplied = "companion-env-7e01d3a95b62"

        credential = resolve_credential(
            COMPANION_KEY,
            root,
            {COMPANION_KEY.env_name: f"  {supplied}  "},
            interpreter_prefix=tmp_path.parent,
        )

        assert credential == Credential(supplied, CredentialSource.ENVIRONMENT)

    def test_only_the_declaring_packages_mode_is_consulted(
        self, tmp_path: Path
    ) -> None:
        # The workspace runs core as a dev dependency, which says nothing
        # about the companion. No caller can nominate the mode the gate
        # consults: the entry's declaring package is the only answer.
        root = _dotenv(_workspace(tmp_path, package=PACKAGE, mode=InstallMode.DEV))

        assert (
            resolve_credential(
                COMPANION_KEY, root, {}, interpreter_prefix=root / ".venv"
            )
            is None
        )

        write_package_declaration(
            root, COMPANION, PackageDeclaration(install_mode=InstallMode.DEV)
        )

        assert resolve_credential(
            COMPANION_KEY, root, {}, interpreter_prefix=root / ".venv"
        ) == Credential(COMPANION_DOTENV_KEY, CredentialSource.DOTENV)


class TestStartupRefusal:
    """Every product value is refused before the work, not after it."""

    def test_a_switch_read_at_output_time_is_checked_up_front(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            check_environment({"VAULTSPEC_NO_HINTS": "maybe"})

        assert str(refusal.value) == (
            f"VAULTSPEC_NO_HINTS must be {BOOL_SHAPE}, got 'maybe'"
        )

    def test_a_field_and_a_switch_are_reported_together(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            check_environment(
                {
                    "VAULTSPEC_IO_BUFFER_SIZE": "plenty",
                    "VAULTSPEC_JSON_PRETTY": "sometimes",
                }
            )

        reported = str(refusal.value)
        assert reported.startswith("2 unusable settings:")
        assert "VAULTSPEC_IO_BUFFER_SIZE" in reported
        assert "VAULTSPEC_JSON_PRETTY" in reported

    def test_usable_and_blank_values_pass(self) -> None:
        check_environment(
            {
                "VAULTSPEC_NO_HINTS": "yes",
                "VAULTSPEC_NON_INTERACTIVE": "  ",
                "VAULTSPEC_IO_BUFFER_SIZE": "4096",
            }
        )

    def test_the_protective_switch_is_exempt(self) -> None:
        # A typo leaves the watchdog armed and warns; refusing to start is
        # not a safer outcome than running guarded.
        check_environment({"VAULTSPEC_STDIO_WATCHDOG": "maybe"})

    def test_an_external_convention_is_not_the_products_to_refuse(self) -> None:
        check_environment({"CI": "whatever", "NO_COLOR": "yes please"})


class TestCheckEnvironmentPerPackage:
    """A companion checks its own entries, not core's whole registry."""

    def test_a_companion_is_blind_to_a_bad_value_that_is_not_its_own(self) -> None:
        # VAULTSPEC_IO_BUFFER_SIZE belongs to core alone; a companion's own
        # startup check must not trip over a variable it never declared.
        check_environment({"VAULTSPEC_IO_BUFFER_SIZE": "plenty"}, package=COMPANION)

    def test_a_companions_own_bad_value_is_refused(self) -> None:
        companion_level = ConfigVariable(
            env_name="VAULTSPEC_RESOLUTION_COMPANION_LEVEL_A",
            attr_name=None,
            var_type=str,
            default=None,
            description="The companion's own level, chained to the shared name.",
            fallback=VAULTSPEC_LOG_LEVEL,
        )
        register_registry(COMPANION, [companion_level])
        try:
            with pytest.raises(ConfigurationError) as refusal:
                check_environment(
                    {companion_level.env_name: "chatty"}, package=COMPANION
                )
            assert companion_level.env_name in str(refusal.value)
        finally:
            forget_registry_for_tests(COMPANION, [companion_level])

    def test_the_framework_entry_a_companions_chain_reaches_is_also_checked(
        self,
    ) -> None:
        # The companion's own name is unset; the bad value sits on the
        # framework name behind it, and the chain still catches it.
        companion_level = ConfigVariable(
            env_name="VAULTSPEC_RESOLUTION_COMPANION_LEVEL_B",
            attr_name=None,
            var_type=str,
            default=None,
            description="The companion's own level, chained to the shared name.",
            fallback=VAULTSPEC_LOG_LEVEL,
        )
        register_registry(COMPANION, [companion_level])
        try:
            with pytest.raises(ConfigurationError) as refusal:
                check_environment({"VAULTSPEC_LOG_LEVEL": "chatty"}, package=COMPANION)
            assert "VAULTSPEC_LOG_LEVEL" in str(refusal.value)
        finally:
            forget_registry_for_tests(COMPANION, [companion_level])

    def test_cores_own_default_is_unchanged(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            check_environment({"VAULTSPEC_LOG_LEVEL": "chatty"})
        assert "VAULTSPEC_LOG_LEVEL" in str(refusal.value)


class TestLogLevel:
    """The level a process logs at, resolved over the one ladder."""

    def test_debug_outranks_everything(self) -> None:
        assert (
            resolve_log_level(
                debug=True, verbose=True, environ={"VAULTSPEC_LOG_LEVEL": "ERROR"}
            )
            == "DEBUG"
        )

    def test_verbose_asks_for_info(self) -> None:
        assert (
            resolve_log_level(verbose=True, environ={"VAULTSPEC_LOG_LEVEL": "ERROR"})
            == "INFO"
        )

    def test_the_variable_answers_when_the_invocation_does_not(self) -> None:
        assert resolve_log_level(environ={"VAULTSPEC_LOG_LEVEL": "error"}) == "ERROR"

    def test_the_callers_own_default_stands_below_the_variable(self) -> None:
        assert resolve_log_level(environ={}) == "WARNING"
        assert resolve_log_level(environ={}, default="INFO") == "INFO"

    def test_a_blank_variable_is_unset(self) -> None:
        assert resolve_log_level(environ={"VAULTSPEC_LOG_LEVEL": "  "}) == "WARNING"

    def test_a_package_level_chains_to_the_framework_name(self) -> None:
        companion = ConfigVariable(
            env_name="VAULTSPEC_RESOLUTION_COMPANION_LOG_LEVEL",
            attr_name=None,
            var_type=str,
            default=None,
            description="The companion's own level, chained to the framework name.",
            fallback=VAULTSPEC_LOG_LEVEL,
        )
        register_registry(COMPANION, [companion])
        try:
            assert (
                resolve_log_level(
                    variable=companion, environ={"VAULTSPEC_LOG_LEVEL": "debug"}
                )
                == "DEBUG"
            )
            assert (
                resolve_log_level(
                    variable=companion,
                    environ={
                        companion.env_name: "critical",
                        "VAULTSPEC_LOG_LEVEL": "debug",
                    },
                )
                == "CRITICAL"
            )
        finally:
            forget_registry_for_tests(COMPANION, [companion])

    def test_an_unknown_level_is_refused_by_name(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            resolve_log_level(environ={"VAULTSPEC_LOG_LEVEL": "chatty"})

        reported = str(refusal.value)
        assert "VAULTSPEC_LOG_LEVEL" in reported
        for level in LOG_LEVELS:
            assert level in reported

    def test_a_callers_own_default_that_is_not_a_level_is_refused(self) -> None:
        """A caller-supplied default outside LOG_LEVELS is a programming error.

        resolve_log_level promises one of LOG_LEVELS back; a caller passing a
        default it cannot honour must fail loudly rather than hand back a
        name nothing downstream (getattr(logging, ...)) can resolve.
        """
        with pytest.raises(ValueError, match="DEBUG"):
            resolve_log_level(environ={}, default="trace")

    def test_an_unknown_level_joins_the_startup_report(self) -> None:
        with pytest.raises(ConfigurationError) as refusal:
            check_environment(
                {"VAULTSPEC_LOG_LEVEL": "chatty", "VAULTSPEC_NO_HINTS": "maybe"}
            )

        reported = str(refusal.value)
        assert reported.startswith("2 unusable settings:")
        assert "VAULTSPEC_LOG_LEVEL" in reported


class TestUnattendedDetection:
    """One rule for whether anybody is there to answer a prompt."""

    def test_the_product_marker_outranks_ci(self) -> None:
        # A wrapper script running under CI with somebody watching says so
        # with the product's own variable, which is the later word.
        assert unattended_declared({"CI": "true"}) is True
        assert unattended_declared(
            {"CI": "true", "VAULTSPEC_NON_INTERACTIVE": "0"}
        ) is (False)
        assert unattended_declared({"VAULTSPEC_NON_INTERACTIVE": "1"}) is True

    def test_nothing_declared_is_not_a_declaration(self) -> None:
        assert unattended_declared({}) is None
        assert unattended_declared({"VAULTSPEC_NON_INTERACTIVE": "  "}) is None

    def test_ci_is_present_even_when_blank(self) -> None:
        assert unattended_declared({"CI": ""}) is True

    def test_an_unreadable_marker_is_refused(self) -> None:
        with pytest.raises(ConfigurationError):
            unattended_declared({"VAULTSPEC_NON_INTERACTIVE": "maybe"})

    def test_a_declared_unattended_run_never_prompts(self) -> None:
        assert is_unattended(
            environ={"VAULTSPEC_NON_INTERACTIVE": "yes"},
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )

    def test_a_machine_envelope_is_unattended_whatever_the_session_says(
        self,
    ) -> None:
        assert is_unattended(
            json_output=True,
            environ={"VAULTSPEC_NON_INTERACTIVE": "0"},
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )

    def test_a_stream_that_is_not_a_terminal_is_unattended(self) -> None:
        # Declaring an operator present does not conjure one: a pipeline is
        # still a pipeline.
        assert is_unattended(
            environ={"VAULTSPEC_NON_INTERACTIVE": "0"},
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )

    def test_a_closed_stream_is_nobody(self) -> None:
        closed = io.StringIO()
        closed.close()

        assert is_unattended(environ={}, stdin=closed, stdout=io.StringIO())
