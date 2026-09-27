# Independent verifier contract

Input schema: `aicg schema verifier-input`. Output envelope schema: `aicg schema external`. Inner report statuses: PASS, REPAIR_REQUIRED, HUMAN_REVIEW_REQUIRED, INSUFFICIENT_EVIDENCE. Every report has failed_criteria, architecture_concerns, security_concerns, missing_evidence and repair_instructions arrays. PASS with any unresolved entry is invalid.

A provider implements `VerifierProvider.verify(request: VerifierInput) -> VerifierReport`. The orchestrating independent service owns credentials, identity verification and the transport. It must review the request's actual source and evidence, then wrap its report in an external envelope using the request's exact run_id, policy_hash and source_hash. `recorded_at` must be a timezone-aware ISO timestamp. `reviewer` identifies the provider or human; v1 records that string but cannot authenticate it.

Example structure (metavariables must be replaced by the independent producer, not the implementation agent):

```json
{
  "schema_version": 1,
  "kind": "verifier",
  "producer": "external",
  "run_id": "<request.run_id>",
  "policy_hash": "<request.policy_hash>",
  "source_hash": "<request.source_hash>",
  "reviewer": "<independent reviewer identity>",
  "recorded_at": "<ISO timestamp with timezone>",
  "report": {
    "status": "INSUFFICIENT_EVIDENCE",
    "failed_criteria": [],
    "architecture_concerns": [],
    "security_concerns": [],
    "missing_evidence": ["Replace this example with an actual independent review"],
    "repair_instructions": []
  }
}
```

Store incoming report files outside the source tree or under ignored run artifacts to avoid changing the source fingerprint before import. `aicg verifier import FILE` imports verifier or runtime external evidence; runner-owned evidence is never accepted. If a runtime command exists, runtime imports are rejected.

No remote calls occur in the CLI. A fixture report is not independent verification. The system prompt in SYSTEM_PROMPT.md is guidance, not evidence or an enforcement mechanism.
