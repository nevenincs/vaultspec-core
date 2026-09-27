---
tags:
  - '#audit'
  - '#reference-publication-contract'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:55c06d940e4529619f9026d46e691e9dc2c59957e548b028ccdd760ef3ffbb78'
related:
  - "[[2026-09-09-reference-publication-contract-adr]]"
  - "[[2026-09-18-release-publication-ordering-adr]]"
---

# `reference-publication-contract` audit: `Published-release claims in the generated references`

## Scope

The version and surface the generated references attribute against: how
`src/vaultspec_core/builtins/reference/published-surface.json` is recorded, where the
rendered claim lands, and the publish lane's surface checks. Triggered by the deployed
`.vaultspec/reference/cli.md` naming `0.2.6` while the bundled reference names `0.3.0`.
Release state was read on 2026-09-27 with `gh release list`, `gh release view`,
`gh run list --workflow=publish.yml`, and the PyPI JSON API.

## Findings

### unpublished-release-claimed | high | main's references name a draft release as the latest published one

`docs/CLI.md:126`, `docs/MCP.md:252`, and
`src/vaultspec_core/builtins/reference/cli.md:54` render "The latest published release is
`0.3.0`". GitHub reports `vaultspec-core-v0.3.0` as a draft with zero assets and
`vaultspec-core-v0.2.6` as the latest release. PyPI serves `0.2.6`, and no `publish.yml`
run exists for `0.3.0`. The open release pull request already renders `0.3.1`.

### candidate-version-stamped-as-published | high | the snapshot version is the candidate's declared version, recorded before any release exists

`.github/workflows/release-please.yml:88` runs `just framework-surface` on the
release-please branch. `spec reference snapshot` captures the live tree and stamps it
with `project_version()` (`src/vaultspec_core/cli/reference_surface.py:94`), which reads
the bumped `pyproject.toml`. The snapshot reaches main with the release merge, so main
calls the candidate published the moment the release pull request merges, whether or not
`publish.yml` ever flips the draft. Under the draft-first ordering that flip is the last
act of `publish.yml`, and every stop before it (0.2.3, 0.2.4, 0.3.0) leaves main naming a
version nobody can install. Nothing that sets the version consults the GitHub release.

### latest-wording-expires | medium | "the latest published release is X" turns false in every frozen copy once a later release publishes

`src/vaultspec_core/cli/reference_gen.py:284` and `src/vaultspec_core/cli/reference_gen.py:353`
render the claim in the present tense. The wheel ships the rendered reference, and
`.vaultspec/reference/cli.md` is a deployed copy whose region still reads `0.2.6` after
`0.3.0` merged - correct only because `0.3.0` never published.

### publish-job-runs-without-checkout | medium | the publish job runs a recipe from whatever justfile the runner's workspace holds

The `publish-pypi` job in `.github/workflows/publish.yml:132` has no checkout step, yet
`.github/workflows/publish.yml:335` runs `just release-verify-surface published`. On the
persistent self-hosted runner that resolves the recipe and the project code from a
workspace an earlier job left behind, inside a job holding `id-token: write`.

### stray-surface-asset | low | the 0.2.6 release carries the smoke test's surface document as an attested asset

`justfile:587` writes `${wheel}.surface.json` beside the wheel in `dist/`. `publish-pypi`
downloads its artifact into the same persistent `dist/`, enumerates `dist` for
attestation (`.github/workflows/publish.yml:198`), and uploads `dist/*`
(`.github/workflows/publish.yml:274`). The `0.2.6` release therefore carries
`vaultspec_core-0.2.6-py3-none-any.whl.surface.json` as an attested, checksummed asset.

## Recommendations

- `unpublished-release-claimed`, `candidate-version-stamped-as-published`: a follow-on
  ADR must decide where the version and surface named by the references come from. The
  findings point at the published GitHub release as the only source that cannot be
  ahead of what users can install.
- `latest-wording-expires`: the same decision must choose wording that stays true in
  the wheel and in deployed copies.
- `publish-job-runs-without-checkout`: the read-back in a job holding an OIDC grant
  should run no project code; compare the attached asset with the built artifact.
- `stray-surface-asset`: write the surface document outside `dist/`.
