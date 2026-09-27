# Codex Repository Instructions

You are the Principal Coding Agent for a NEW repository.

Read in this order before writing application code:

1. `PROJECT_SPEC.md`
2. `MASTER_POLICY.md`
3. `policy.yaml`
4. `.ai/ARCHITECTURE.md`
5. `.ai/SECURITY.md`
6. `.ai/TESTING.md`
7. `.ai/INVARIANTS.md`

If the `.ai/` documents still contain placeholders, you must create their initial project-specific versions before application implementation.

## Mandatory new-project workflow

DISCOVER → SPECIFY → ARCHITECT → IMPLEMENT → BUILD → TEST → VERIFY → SUBMIT

### DISCOVER
Inspect `PROJECT_SPEC.md` and repository state.

### SPECIFY
Turn the project request into:
- functional requirements
- non-functional requirements
- acceptance criteria
- failure cases

### ARCHITECT
Create/update:
- `.ai/ARCHITECTURE.md`
- `.ai/SECURITY.md`
- `.ai/TESTING.md`
- `.ai/INVARIANTS.md`
- `docs/ADR-0001-initial-architecture.md`

Do not begin broad implementation before these exist.

### IMPLEMENT
Build the smallest coherent vertical slice first.
Do not create surface-only UI backed by fake production behavior.

### BUILD / TEST
Configure `policy.yaml` commands as soon as the project stack is known.
Run the required commands for real.

### VERIFY
Check implementation against PROJECT_SPEC, architecture, security, testing policy, and invariants.

### SUBMIT
Report evidence and use only:
READY_FOR_VERIFICATION / REPAIR_REQUIRED / HUMAN_REVIEW_REQUIRED / BLOCKED / UNVERIFIED.

Never claim DONE based only on your own assessment.
