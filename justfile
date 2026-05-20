set positional-arguments := false
set shell := ["sh", "-cu"]
set windows-shell := ["pwsh.exe", "-NoProfile", "-c"]

image := "ghcr.io/wgergely/vaultspec-core"
local_image := "vaultspec-core:local"

default:
  @echo "Available commands:"
  @echo "  prod [args...]    Run the vaultspec-core Python CLI (pure 1:1 mirror)"
  @echo "  dev <target>      Development toolchain (deps, lint, fix, audit, test, build, etc.)"
  @echo "  ci                Full CI pipeline: lint → audit → vault check → test"
  @echo ""
  @echo "Run 'just <command> --help' for more details."

# ===========================================================================
#  prod  - pure 1:1 mirror of the vaultspec-core Python CLI
# ===========================================================================

prod *args='':
  @{{ if args == "--help" { "just _prod-help" } else if args == "-h" { "just _prod-help" } else if args == "help" { "just _prod-help" } else { "uv run vaultspec-core " + args } }}

_prod-help:
  @echo "Usage: just prod [args...]"
  @echo ""
  @echo "Runs the vaultspec-core Python CLI (pure 1:1 mirror)."
  @echo "Examples:"
  @echo "  just prod install . claude --force"
  @echo "  just prod sync claude --dry-run"
  @echo "  just prod vault check all --fix"
  @echo "  just prod vault check all -v"
  @echo "  just prod vault graph --metrics"
  @echo "  just prod vault add adr -f my-feature"
  @echo "  just prod spec rules list"

# ===========================================================================
#  dev  - development toolchain (linters, formatters, tests, builds)
# ===========================================================================

dev target='--help' *args='':
  @{{ if target == "--help" { "just _dev-help" } else if target == "-h" { "just _dev-help" } else if target == "help" { "just _dev-help" } else { "just _dev-" + target + " " + args } }}

_dev-help:
  @echo "Usage: just dev <target> [args...]"
  @echo ""
  @echo "Targets:"
  @echo "  deps      dependency management (sync, upgrade, lock)"
  @echo "  lint      read-only static analysis (ruff, ty, taplo, markdownlint, ...)"
  @echo "  fix       auto-fix everything fixable (python, toml, markdown, vault)"
  @echo "  audit     supply-chain / security checks (uv audit)"
  @echo "  test      pytest, docker smoke"
  @echo "  build     uv build, docker build"
  @echo "  publish   docker push"
  @echo "  precommit pre-commit hook management (install, upgrade, run)"

# ===========================================================================
#  ci  - full pipeline: lint → audit → vault check → test
# ===========================================================================

ci *args='':
  @{{ if args == "--help" { "just _ci-help" } else if args == "-h" { "just _ci-help" } else if args == "help" { "just _ci-help" } else { "just _ci-run" } }}

_ci-help:
  @echo "Usage: just ci"
  @echo ""
  @echo "Runs the full CI pipeline: lint → audit → vault check → test"

_ci-run:
  just dev lint all
  just dev audit deps
  just prod vault check all
  just dev test all

# ---------------------------------------------------------------------------
#  Internal recipes (prefixed with _ to hide from --list)
# ---------------------------------------------------------------------------

_dev-deps target='--help':
  @{{ if target == "--help" { "just _dev-deps-help" } else if target == "-h" { "just _dev-deps-help" } else if target == "help" { "just _dev-deps-help" } else { "just _dev-deps-" + target } }}

_dev-deps-help:
  @echo "Usage: just dev deps <target>"
  @echo ""
  @echo "Targets:"
  @echo "  sync          Sync dependencies"
  @echo "  upgrade       Upgrade all dependencies"
  @echo "  lock          Lock dependencies"
  @echo "  lock-upgrade  Upgrade and lock dependencies"

_dev-deps-sync:
  uv sync --locked --group dev

_dev-deps-upgrade:
  uv sync --upgrade --all-groups

_dev-deps-lock:
  uv lock

_dev-deps-lock-upgrade:
  uv lock --upgrade

# ---------------------------------------------------------------------------

_dev-lint target='--help':
  @{{ if target == "--help" { "just _dev-lint-help" } else if target == "-h" { "just _dev-lint-help" } else if target == "help" { "just _dev-lint-help" } else { "just _dev-lint-" + target } }}

_dev-lint-help:
  @echo "Usage: just dev lint <target>"
  @echo ""
  @echo "Targets:"
  @echo "  python    Run Ruff on Python source"
  @echo "  type      Run Ty (type checker) on Python source"
  @echo "  links     Run Lychee link checker"
  @echo "  toml      Run Taplo TOML linter"
  @echo "  markdown  Run Markdown linting and formatting checks"
  @echo "  workflow  Run Actionlint on GitHub workflows"
  @echo "  all       Run all linters"

_dev-lint-python:
  uv run ruff check src tests
  uv run ruff format --check src tests

_dev-lint-type:
  uv run python -m ty check src/vaultspec_core

_dev-lint-links:
  @{{ if os() == "windows" { \
    "if (Get-Command lychee -ErrorAction SilentlyContinue) { lychee --config lychee.toml README.md .vault .vaultspec } elseif (Get-Command docker -ErrorAction SilentlyContinue) { docker run --rm -v '${PWD}:/repo' -w /repo lycheeverse/lychee:latest --config /repo/lychee.toml README.md .vault .vaultspec } else { Write-Error 'lychee not found and docker is unavailable'; exit 127 }" \
  } else { \
    "if command -v lychee >/dev/null 2>&1; then lychee --config lychee.toml README.md .vault .vaultspec; elif command -v docker >/dev/null 2>&1; then docker run --rm -v \"$PWD:/repo\" -w /repo lycheeverse/lychee:latest --config /repo/lychee.toml README.md .vault .vaultspec; else echo 'lychee not found and docker is unavailable' >&2; exit 127; fi" \
  } }}

_dev-lint-toml:
  @{{ if os() == "windows" { \
    "if (Get-Command taplo -ErrorAction SilentlyContinue) { taplo lint *.toml } elseif (Get-Command docker -ErrorAction SilentlyContinue) { docker run --rm -v '${PWD}:/repo' -w /repo tamasfe/taplo:0.9 lint *.toml } else { Write-Error 'taplo not found and docker is unavailable'; exit 127 }" \
  } else { \
    "if command -v taplo >/dev/null 2>&1; then taplo lint *.toml; elif command -v docker >/dev/null 2>&1; then docker run --rm -v \"$PWD:/repo\" -w /repo tamasfe/taplo:0.9 lint *.toml; else echo 'taplo not found and docker is unavailable' >&2; exit 127; fi" \
  } }}

_dev-lint-markdown:
  uv run mdformat --check README.md .vaultspec/ .vault/
  uv run mdformat --wrap 88 --check README.md .vaultspec/README.md .vaultspec/MCP.md .vaultspec/CLI.md .vaultspec/rules
  uv run pymarkdown --config .pymarkdown.json scan -r README.md .vaultspec/ .vault/

_dev-lint-workflow:
  @{{ if os() == "windows" { \
    "if (Get-Command actionlint -ErrorAction SilentlyContinue) { actionlint } elseif (Get-Command docker -ErrorAction SilentlyContinue) { docker run --rm -v '${PWD}:/repo' -w /repo rhysd/actionlint:latest } else { Write-Error 'actionlint not found and docker is unavailable'; exit 127 }" \
  } else { \
    "if command -v actionlint >/dev/null 2>&1; then actionlint; elif command -v docker >/dev/null 2>&1; then docker run --rm -v \"$PWD:/repo\" -w /repo rhysd/actionlint:latest; else echo 'actionlint not found and docker is unavailable' >&2; exit 127; fi" \
  } }}

_dev-lint-all:
  just _dev-lint-python
  just _dev-lint-type
  just _dev-lint-links
  just _dev-lint-toml
  just _dev-lint-markdown
  just _dev-lint-workflow

# ---------------------------------------------------------------------------

_dev-fix target='--help':
  @{{ if target == "--help" { "just _dev-fix-help" } else if target == "-h" { "just _dev-fix-help" } else if target == "help" { "just _dev-fix-help" } else { "just _dev-fix-" + target } }}

_dev-fix-help:
  @echo "Usage: just dev fix <target>"
  @echo ""
  @echo "Targets:"
  @echo "  python    Auto-fix and format Python source"
  @echo "  toml      Auto-format TOML files"
  @echo "  markdown  Auto-format Markdown files"
  @echo "  vault     Auto-fix vault issues"
  @echo "  all       Run all fixers"

_dev-fix-python:
  uv run ruff format src tests
  uv run ruff check --fix src tests

_dev-fix-toml:
  @{{ if os() == "windows" { \
    "if (Get-Command taplo -ErrorAction SilentlyContinue) { taplo fmt *.toml } elseif (Get-Command docker -ErrorAction SilentlyContinue) { docker run --rm -v '${PWD}:/repo' -w /repo tamasfe/taplo:0.9 fmt *.toml } else { Write-Error 'taplo not found and docker is unavailable'; exit 127 }" \
  } else { \
    "if command -v taplo >/dev/null 2>&1; then taplo fmt *.toml; elif command -v docker >/dev/null 2>&1; then docker run --rm -v \"$PWD:/repo\" -w /repo tamasfe/taplo:0.9 fmt *.toml; else echo 'taplo not found and docker is unavailable' >&2; exit 127; fi" \
  } }}

_dev-fix-markdown:
  uv run mdformat README.md .vaultspec/ .vault/
  uv run mdformat --wrap 88 README.md .vaultspec/README.md .vaultspec/MCP.md .vaultspec/CLI.md .vaultspec/rules
  uv run pymarkdown --config .pymarkdown.json fix -r README.md .vaultspec/ .vault/

_dev-fix-vault:
  uv run vaultspec-core vault check all --fix
  uv run vaultspec-core vault sanitize annotations

_dev-fix-all:
  just _dev-fix-python
  just _dev-fix-toml
  just _dev-fix-markdown
  just _dev-fix-vault

# ---------------------------------------------------------------------------

_dev-audit target='--help':
  @{{ if target == "--help" { "just _dev-audit-help" } else if target == "-h" { "just _dev-audit-help" } else if target == "help" { "just _dev-audit-help" } else { "just _dev-audit-" + target } }}

_dev-audit-help:
  @echo "Usage: just dev audit <target>"
  @echo ""
  @echo "Targets:"
  @echo "  deps      Run uv audit on locked dependencies"

# uv audit is the uv-native vulnerability scanner; --preview-features audit
# silences its experimental warning.  The audit's default scope already
# includes the project plus the default dependency groups (dev), which is
# all groups in this project, so we don't pass --all-groups: that flag was
# accepted by uv 0.10.x but rejected by 0.11.x where the in-flight audit
# CLI tightened to single-group selection.  The wrapper greps for the
# clean-summary line ("Found no known vulnerabilit..." or "Found 0 ...")
# because uv 0.10.x/0.11.x exit 0 even when advisories are present; drop
# the wrapper once `uv audit --strict` (or equivalent) ships and exits
# non-zero on findings.
#
# --ignore PYSEC-2025-183 (alias CVE-2025-45768): a pyjwt advisory
# claiming "weak encryption". It is DISPUTED by pyjwt's maintainer
# (the OSV record states the dispute: key length is chosen by the
# application, not the library) and its affected range covers EVERY
# pyjwt release (introduced at 0, no fixed event) -- there is no
# version to upgrade to. pyjwt is a transitive dependency pulled by
# `mcp` (the MCP SDK behind vaultspec-mcp), which hard-depends on
# `pyjwt[crypto]` and cannot be dropped. A blanket --ignore is used
# rather than --ignore-until-fixed because the advisory's OSV range
# is malformed (an empty event object), which prevents uv from
# evaluating fix-availability; and because, being disputed and
# unfixed across all versions, no fix is expected. Revisit this
# entry if pyjwt ships a release that resolves or the advisory is
# withdrawn.
_dev-audit-deps:
  @{{ if os() == "windows" { \
    "$out = uv audit --preview-features audit --frozen --ignore PYSEC-2025-183 --ignore CVE-2025-45768 2>&1 | Out-String; Write-Host $out; if ($out -notmatch 'Found (no|0) known vulnerabilit') { exit 1 }" \
  } else { \
    "out=$(uv audit --preview-features audit --frozen --ignore PYSEC-2025-183 --ignore CVE-2025-45768 2>&1); printf '%s\\n' \"$out\"; printf '%s\\n' \"$out\" | grep -Eq 'Found (no|0) known vulnerabilit' || exit 1" \
  } }}

# ---------------------------------------------------------------------------

_dev-test target='--help':
  @{{ if target == "--help" { "just _dev-test-help" } else if target == "-h" { "just _dev-test-help" } else if target == "help" { "just _dev-test-help" } else { "just _dev-test-" + target } }}

_dev-test-help:
  @echo "Usage: just dev test <target>"
  @echo ""
  @echo "Targets:"
  @echo "  python    Run pytest on Python source"
  @echo "  docker    Run smoke test in Docker"
  @echo "  all       Run all tests"

_dev-test-python:
  uv run pytest src/vaultspec_core -x -q --tb=short -m "unit and not gemini and not claude"

_dev-test-docker:
  just _dev-build-docker
  docker run --rm {{ local_image }} vaultspec-core --help

_dev-test-all:
  just _dev-test-python
  just _dev-test-docker

# ---------------------------------------------------------------------------

_dev-build target='--help':
  @{{ if target == "--help" { "just _dev-build-help" } else if target == "-h" { "just _dev-build-help" } else if target == "help" { "just _dev-build-help" } else { "just _dev-build-" + target } }}

_dev-build-help:
  @echo "Usage: just dev build <target>"
  @echo ""
  @echo "Targets:"
  @echo "  python    Build Python package"
  @echo "  docker    Build Docker image locally"
  @echo "  all       Run all builds"

_dev-build-python:
  uv build

_dev-build-docker:
  docker buildx build --load -t {{ local_image }} .

_dev-build-all:
  just _dev-build-python
  just _dev-build-docker

# ---------------------------------------------------------------------------

_dev-publish target='--help' tag='':
  @{{ if target == "--help" { "just _dev-publish-help" } else if target == "-h" { "just _dev-publish-help" } else if target == "help" { "just _dev-publish-help" } else { "just _dev-publish-" + target + " " + tag } }}

_dev-publish-help:
  @echo "Usage: just dev publish <target> <tag>"
  @echo ""
  @echo "Targets:"
  @echo "  docker-ghcr   Publish docker image to GHCR"

_dev-publish-docker-ghcr tag:
  @{{ if os() == "windows" { \
    "if (-not '" + tag + "') { Write-Error \"error: missing argument 'tag' for docker-ghcr\"; exit 1 }; docker buildx build --platform linux/amd64 --push -t " + image + ":" + tag + " ." \
  } else { \
    "if [ -z '" + tag + "' ]; then echo \"error: missing argument 'tag' for docker-ghcr\" >&2; exit 1; fi; docker buildx build --platform linux/amd64 --push -t " + image + ":" + tag + " ." \
  } }}

# ---------------------------------------------------------------------------

_dev-precommit target='--help':
  @{{ if target == "--help" { "just _dev-precommit-help" } else if target == "-h" { "just _dev-precommit-help" } else if target == "help" { "just _dev-precommit-help" } else { "just _dev-precommit-" + target } }}

_dev-precommit-help:
  @echo "Usage: just dev precommit <target>"
  @echo ""
  @echo "Targets:"
  @echo "  install   Install pre-commit hooks"
  @echo "  upgrade   Upgrade pre-commit hooks"
  @echo "  run       Run pre-commit hooks on all files"

_dev-precommit-install:
  uv run prek install

_dev-precommit-upgrade:
  uv run prek auto-update

_dev-precommit-run:
  uv run prek run --all-files
