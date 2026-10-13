## Purpose and acceptance criteria

- Scope and reason for the change:
- Acceptance criteria / failure cases:
- Base branch and reviewed commit:

## Evidence (never claim checks ran unless they did)

| Check | Result (passed / failed / not run / N/A + reason) | Run or log URL / evidence |
| --- | --- | --- |
| Build and runtime | | |
| Unit/integration/negative tests | | |
| Lint and type checks | | |
| Security/dependency checks | | |
| `aicg gate run` | | |
| `aicg gate final` | | |
| Required protected CI check and expected source | | |

## Independent review and safety

- Reviewer separate from implementer; concerns and follow-up (or **not done**):
- External signed verifier attestation, **only if required by policy** (or **not required**):
- Sensitive data, authentication, migration, deployment or destructive actions? If yes, list explicit human approvals.
- Did this PR change tests, policy, CI files, workflow permissions or trusted verification configuration? If yes, explain how bypasses were excluded.
- Any unresolved `BLOCKED` / `REPAIR_REQUIRED` / `UNVERIFIED` items:

## Release decision

- [ ] Changes remain on a reviewable branch; no direct protected-branch edits.
- [ ] Required checks are current for the PR head and externally enforced; otherwise state what is unverified.
- [ ] Human reviewer approves merge only after inspecting the evidence.

Guidance: [Codex + Warp evidence workflow](../docs/CODEX_WARP_EVIDENCE_WORKFLOW.md). Agent self-assessment and a manually typed `PASS` do not replace objective evidence.
