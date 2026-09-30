---
tags:
  - '#exec'
  - '#release-standard'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:a4edda104b15ea92ccf95f485e8c27334acaf1d4b1420f261f97f4c51e995488'
related:
  - "[[2026-09-30-release-standard-plan]]"
---

# `release-standard` ledger

## Changes

- `S01` `A` `.vault/research/2026-09-30-release-standard-research.md`
- `S01` `A` `.vault/adr/2026-09-30-release-standard-adr.md`
- `S01` `M` `.vault/adr/2026-03-22-clci-release-adr.md`
- `S01` `M` `.vault/adr/2026-09-18-release-publication-ordering-adr.md`
- `S01` `verify:` `vaultspec-core vault check all` -> `pass`
- `S02` `M` `.github/workflows/release-please.yml`
- `S02` `M` `release-please-config.json`
- `S02` `M` `.github/ci-contract-allow.txt`
- `S02` `M` `.github/workflows/merge-gate.yml`
- `S02` `verify:` `just check-workflow` -> `pass`
- `S02` `verify:` `shellcheck -s bash release-please.yml run blocks` -> `pass`
- `S03` `D` `.github/workflows/release.yml`
- `S03` `M` `.github/workflows/binaries.yml`
- `S03` `verify:` `just check-workflow` -> `pass`
- `S04` `M` `dev/guards/test_automation_contracts.py`
- `S04` `verify:` `pytest dev/guards` -> `pass`
- `S04` `verify:` `guard mutation proofs for the two rewritten release guards` -> `pass`
- `S05` `M` `docs/README.md`
- `S05` `verify:` `just check-markdown` -> `pass`
- `S05` `verify:` `just check-links` -> `pass`
- `S10` `M` `.github/workflows/merge-gate.yml`
- `S10` `verify:` `just check-workflow` -> `pass`
- `S10` `verify:` `shellcheck -s bash merge-gate.yml gate run blocks` -> `pass`
- `S11` `M` `dev/guards/test_ci_check_shape.py`
- `S11` `verify:` `pytest dev/guards` -> `pass`
- `S11` `verify:` `guard mutation proofs for the author clause and the untrusted refusal` -> `pass`
- `S12` `M` `.github/workflows/model-drift.yml`
- `S12` `verify:` `just check-workflow` -> `pass`
- `S13` `M` `.github/workflows/main-health.yml`
- `S13` `verify:` `just check-workflow` -> `pass`
- `S10` `M` `dev/guards/test_ci_check_shape.py`
- `S10` `verify:` `pytest dev/guards/test_ci_check_shape.py` -> `pass`
- `S10` `verify:` `guard mutation proofs for the author clause and the untrusted refusal` -> `pass`
- `S14` `M` `GitHub settings nevenincs/vaultspec-core`
- `S14` `verify:` `gh api repos/nevenincs/vaultspec-core/actions/permissions/workflow` -> `pass`
- `S14` `verify:` `gh api repos/nevenincs/vaultspec-core/rulesets` -> `pass`
- `S06` `M` `vaultspec-rag .github/workflows/release-please.yml`
- `S06` `verify:` `pytest dev/guards in vaultspec-rag` -> `pass`
- `S07` `M` `vaultspec-a2a .github/workflows/release-please.yml`
- `S07` `verify:` `just ci-merge in vaultspec-a2a` -> `pass`
- `S08` `M` `vaultspec-dashboard .github/workflows/release-please.yml`
- `S08` `verify:` `pytest dev/guards in vaultspec-dashboard` -> `pass`
- `S09` `M` `vaultspec-marketing .github/workflows/release-please.yml`
- `S09` `verify:` `pytest in vaultspec-marketing` -> `pass`
- `S02` `M` `.github/workflows/acquisition.yml`
- `S02` `M` `.github/workflows/publish.yml`
- `S02` `verify:` `just check-workflow` -> `pass`
- `S04` `verify:` `pytest dev/guards` -> `pass`
- `S04` `verify:` `guard mutation proof for the tree-wide tag and release trigger check` -> `pass`

## Notes

- `S02` S02, S03 and S04 share one commit: the cut, the retired relay and the rewritten guards only pass together
- `S10` S10 and S11 share one commit: the guard fails without the rule it pins
- `S10` the author clause is written as two equality comparisons rather than contains(fromJSON()), so every repository's guard evaluator can decide it
- `S14` token cannot approve pull requests; SHA-pinned actions required; pypi deployments from main only; deploy-key bypass removed from both rulesets; the unused write deploy key scoop-manifest-bump-ci and the unreferenced `SCOOP_DEPLOY_KEY` and `ADD_TO_PROJECT_PAT` secrets deleted; `DEV_RUNNER_PAT` and `FLEET_PREFLIGHT_TOKEN` kept because workflows use them
- `S06` landed as nevenincs/vaultspec-rag#568: draft-first release with publication last, channels and acquisition after publication, the trusted-author rule, and the cut's diagnosis step
- `S07` landed as nevenincs/vaultspec-a2a#91: dispatched cut, release.yml dispatch-only, trusted-author rule on every pull-request lane, MEMBER dropped from claude.yml
- `S08` landed as nevenincs/vaultspec-dashboard#157 and #159: dispatched cut without the release PAT, gate never skipped, no workspace code before checkout, trusted-author rule; the two remaining guard failures predate it on main
- `S09` landed as nevenincs/vaultspec-marketing#14 and #15: dispatched cut onto a draft the site lane publishes last, trusted-author rule; the dev-server trust clause landed at its source as nevenincs/devservers#3
- `S02` review correction: acquisition.yml no longer starts from a release event; the publication lane dispatches it
- `S04` review correction: the dispatch-only guard now walks every workflow
