---
tags:
  - '#research'
  - '#publisher-identity'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:09f431b63f2a1abb4f6f278b3a662eff1e8f95babf21ac4f618eced009375685'
related: []
---

# `publisher-identity` research: `what signing a release binary costs, and what it buys`

Whether the released binaries can carry a publisher identity, and what changes if they
do. vaultspec-core#342 measured the Windows artifacts as unsigned and vaultspec-core#336
measured the macOS ones as ad-hoc signed; both proposed remediations that the current
certificate market no longer supports. The evidence below is that the remediation named
in those issues is unbuyable as written, that one free route exists whose price is
process rather than money, and that a second, weaker guarantee is available immediately
and needs no identity at all. What must still be settled is which of those the project
adopts and what it records about the gap that remains.

## Findings

### A publicly-trusted signing key can no longer be held in a repository secret

vaultspec-core#342 proposes storing a PFX as a base64 repository secret alongside its
password. No CA can issue a certificate in that form. Since 2023-06-01 the CA/Browser
Forum Baseline Requirements for Code Signing oblige every publicly-trusted code-signing
key - OV as well as EV, where previously only EV was covered - to be generated in and
non-exportable from hardware meeting FIPS 140-2 level 2 or Common Criteria EAL4+. CAs
withdrew browser-based key generation and PFX delivery to comply.
https://www.encryptionconsulting.com/understanding-the-ca-browser-forum-code-signing-requirements/

The practical consequence is that signing from CI now requires either a hardware token
physically present on the builder, or a hosted signing service holding the key. A secret
pair of the shape #342 asks for can only come from a self-signed certificate.

### EV no longer buys the SmartScreen behaviour the remediation assumed

vaultspec-core#342 justifies an EV certificate on immediate SmartScreen reputation.
Microsoft removed that property in 2024; OV and EV now accrue reputation identically,
per file and per publisher identity, over successive releases.
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation

Reputation accruing to an identity is the part that does not self-heal: a project
releasing under no identity accrues nothing, so every release starts from zero
indefinitely rather than improving with age.

### A free route exists, and its price is process

SignPath Foundation signs open-source projects at no charge with an OV certificate whose
private key it holds in its own HSM, which answers the funding constraint and the
hardware requirement above in one step. Its published conditions require an OSI-approved
licence without commercial dual-licensing, no proprietary components, a repository owned
by the signing team, builds that are automated and verifiable, a project already released
in the form to be signed, and that the software is not a security-diagnosis tool. It
further requires a published code-signing policy naming Authors, Reviewers and Approvers,
multi-factor authentication across the team, and manual approval of each signed release.
https://signpath.org/terms

This repository is MIT-licensed (`LICENSE`), public, and builds its artifacts through
`.github/workflows/binaries.yml`. The remaining conditions are process obligations rather
than costs. Acceptance is decided by human review over days to weeks and is not
guaranteed; nothing in the conditions promises a project of any particular size.

### The paid alternatives are cheap but each carries a structural cost

Certum issues an open-source code-signing certificate from roughly $29, but delivery is
to a physical cryptographic card requiring a reader and the proCertum CardManager
application, so signing binds to one machine rather than to a workflow.
https://certum.store/open-source-code-signing-code.html

Azure Artifact Signing, formerly Trusted Signing, is a hosted signing service at $9.99
per month for up to 5,000 signatures with a first-party GitHub Actions integration. Its
eligibility is geographically bounded and differs for organisations and individuals,
which makes availability a precondition to be checked rather than assumed.
https://azure.microsoft.com/en-us/pricing/details/trusted-signing/

### A self-signed certificate changes the reported status and nothing else

Windows trusts no chain that does not terminate in the Microsoft Trusted Root Program, so
a self-signed Authenticode signature does not make `Get-AuthenticodeSignature` report
`Valid`; it reports an untrusted-root failure instead. SmartScreen reputation attaches to
a CA-validated identity and is unmoved. A WDAC publisher rule cannot name an untrusted
signer, leaving per-file hash rules, which is the same position as unsigned.

### Provenance attestation is available now and answers a different question

GitHub artifact attestations bind an artifact digest to the repository and workflow run
that produced it, signed through Sigstore with a short-lived certificate, and are
verified with `gh attestation verify`. They require no certificate, no purchased
identity, and no per-release cost.
https://docs.github.com/en/actions/concepts/security/artifact-attestations

They are not a substitute for Authenticode. Sigstore's Fulcio is not in the Microsoft
Trusted Root Program, so an attestation moves nothing in SmartScreen, Gatekeeper, or a
WDAC policy. What it changes is the verification a user can perform: `SHA256SUMS` alone
establishes only that a download matches a manifest published beside it, which a tampered
release satisfies equally.

### macOS carries a cost floor Windows does not

The free and low-cost routes above are Authenticode only. A Developer ID signature and
notarization require Apple Developer Program membership at $99 per year, so
vaultspec-core#336 cannot be resolved by the same decision that resolves #342 even if
that decision costs nothing.

### The exposure is narrower than unsigned status alone suggests

vaultspec-core#342 measured that Mark-of-the-Web does not block console execution of the
Windows binary. `.github/workflows/acquisition.yml` records that Scoop clears the mark
for the user, and Scoop is the only Windows binary channel `README.md` documents. The
exposed paths are therefore a browser download launched from Explorer, and managed fleets
running WDAC or AppLocker, where unsigned executables are commonly refused outright and a
publisher rule is the only durable expression of an allowance.

### What was not investigated

The SmartScreen interstitial itself was not exercised, in #342 or here: it is an
interactive Explorer path and the fleet has no way to drive it. Signature status is
measurable; the dialog is not. WDAC and AppLocker refusal was likewise not reproduced, as
no host in the fleet runs such a policy. Reputation accrual rates after a first signed
release were not investigated and are not published by Microsoft in measurable form.

## Sources

- https://www.encryptionconsulting.com/understanding-the-ca-browser-forum-code-signing-requirements/
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- https://signpath.org/terms
- https://certum.store/open-source-code-signing-code.html
- https://azure.microsoft.com/en-us/pricing/details/trusted-signing/
- https://docs.github.com/en/actions/concepts/security/artifact-attestations
- `LICENSE`, `README.md`, `.github/workflows/binaries.yml`,
  `.github/workflows/acquisition.yml`
- vaultspec-core#342, vaultspec-core#336, vaultspec-core#405
