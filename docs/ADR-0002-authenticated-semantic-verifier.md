# ADR-0002: authenticated semantic verifier

Status: accepted. External activation remains pending.

## Context

External verifier evidence previously used a free-text reviewer name and source/policy/run hashes. Anyone able to write evidence could therefore claim `PASS`, and the request's included gate evidence was not independently hashed. The target CI also executes candidate-controlled application code, so it cannot safely receive model or signing credentials.

## Decision

Use an Ed25519-signed, domain-separated canonical JSON attestation. It identifies the stable verifier issuer and key, provider/model, structured report, current run/policy/source hashes, and SHA-256 digest of the exact `VerifierInput`. The report schema rejects PASS with unresolved concerns. Runtime evidence retains its existing import semantics.

Implement one free-tier provider using Cloudflare Workers AI with a fixed model identifier. The provider uses the standard library HTTP client, explicit request and output bounds, strict response parsing, and no automatic fallback to paid plans. API account IDs and tokens remain runtime configuration and are never stored in the repository.

Keep the private signing key and provider token in Buildkite's secret store, accessible only to a fixed verifier step from the protected external pipeline. That step reads the PR snapshot as data and does not execute it. Pin the expected public-key fingerprint and trusted issuer in protected external configuration; the copy in target `policy.yaml` is for local verification, not the CI trust root.

## Consequences

- Unsigned and legacy verifier reports cannot satisfy a required verifier gate.
- Free-tier quota exhaustion, invalid model output, or provider unavailability fails closed.
- A model report authenticates the configured verifier job and reviewed request, not correctness of the model judgment.
- Live activation requires a user-owned Cloudflare Workers AI token and Buildkite secret configuration; no paid provider is assumed.
