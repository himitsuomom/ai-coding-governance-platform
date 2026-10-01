# Independent verifier contract

Input schema: `aicg schema verifier-input`. Signed verifier envelope schema: `aicg schema verifier-attestation`. Runtime external evidence uses `aicg schema external`. Inner report statuses are `PASS`, `REPAIR_REQUIRED`, `HUMAN_REVIEW_REQUIRED`, and `INSUFFICIENT_EVIDENCE`. Every report has failed_criteria, architecture_concerns, security_concerns, missing_evidence and repair_instructions arrays. PASS with any unresolved entry is invalid.

A provider implements `VerifierProvider.verify(request: VerifierInput) -> VerifierReport`. The signing process must be a trusted executable outside PR-controlled code, and its Ed25519 private key must never be given to the implementation job. Configure `policy.verifier.issuer`, `key` (base64 raw public key), `provider` and `model` together. Trusted CI must pin the public-key fingerprint and issuer outside PR-editable files.

The signed payload includes exact `run_id`, `policy_hash`, `source_hash`, `request_hash` (SHA-256 of the complete canonical `VerifierInput`), issuer, key ID, provider, model, timestamp and report. Signature input is `aicg-verifier-attestation-v2\0` followed by canonical JSON without the `signature` field. Unsigned v1 verifier reports, an unknown key, a mismatched request digest, or a changed field are rejected. The key ID is lowercase SHA-256 of the raw 32-byte public key.

Example structure (values are supplied by an independent verifier; signature abbreviated):

```json
{
  "schema_version": 2,
  "kind": "verifier",
  "producer": "aicg-signed-verifier",
  "run_id": "<request.run_id>",
  "policy_hash": "<request.policy_hash>",
  "source_hash": "<request.source_hash>",
  "issuer": "<stable trusted verifier issuer>",
  "key_id": "<sha256(raw public key)>",
  "provider": "cloudflare-workers-ai",
  "model": "@cf/google/gemma-4-26b-a4b-it",
  "request_hash": "<sha256(canonical complete verifier request)>",
  "recorded_at": "<ISO timestamp with timezone>",
  "signature": "<base64 Ed25519 signature>",
  "report": {
    "status": "INSUFFICIENT_EVIDENCE",
    "failed_criteria": [],
    "architecture_concerns": [],
    "security_concerns": [],
    "missing_evidence": ["Replace with an actual independent review"],
    "repair_instructions": []
  }
}
```

Store incoming reports outside the source tree or under ignored run artifacts. `aicg verifier import FILE` validates the signed verifier evidence; runtime import remains unsigned v1 evidence and is rejected if a runtime command exists.

`aicg verifier run` calls only the configured Cloudflare Workers AI model and signs/imports the result. Set `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and base64 `AICG_VERIFIER_PRIVATE_KEY` in a trusted process only. The Free plan currently allocates 10,000 Neurons/day; quota/provider errors fail closed and are never routed to a paid provider. See [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) and [REST API setup](https://developers.cloudflare.com/workers-ai/get-started/rest-api/).

A fixture report is not independent verification. The system prompt is guidance, not evidence or an enforcement mechanism. A valid signature authenticates the configured issuer and exact request; it does not prove the model is correct or that code is benign.
