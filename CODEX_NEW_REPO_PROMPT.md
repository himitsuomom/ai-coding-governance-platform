# Codex — Build the AI Coding Governance Platform

You are creating a NEW repository from this governance template.

## New repository name

Create:

`ai-coding-governance-platform`

If that directory already exists and is non-empty, create a safe alternative and report the actual path. Never overwrite an unrelated repository.

## Objective

Build the software described in `PROJECT_SPEC.md`.

This is a real implementation task, not a design-only task.

The product is a model-independent governance layer for AI coding agents. It must enforce completion through policy, evidence, independent verification, and deterministic CI gates.

## Bootstrap

1. Create the new repository directory.
2. Initialize Git.
3. Copy these governance/source specification files into it:
   - `PROJECT_SPEC.md`
   - `MASTER_POLICY.md`
   - `policy.yaml`
   - `AGENTS.md`
   - `.ai/`
   - `verifier/`
   - `.github/`
4. Read all copied policy/specification files before implementation.

## Mandatory workflow

DISCOVER
→ SPECIFY
→ ARCHITECT
→ IMPLEMENT
→ BUILD
→ TEST
→ VERIFY
→ SUBMIT

If a check fails:

DIAGNOSE
→ REPAIR
→ BUILD / TEST / VERIFY

## Before application implementation

Create or replace the placeholders with project-specific content:

- `.ai/ARCHITECTURE.md`
- `.ai/SECURITY.md`
- `.ai/TESTING.md`
- `.ai/INVARIANTS.md`
- `docs/ADR-0001-initial-architecture.md`

Choose the smallest production-capable stack that satisfies `PROJECT_SPEC.md`.

Do not build a web UI unless needed by an acceptance criterion.

Do not implement a custom LLM, custom sandbox, vector database, graph database, distributed orchestrator, or model training system for v1.

## Implementation priority

Implement in this order:

1. package/repository structure
2. policy schema + validation
3. workflow state model
4. evidence schema/store
5. deterministic gate engine
6. CLI
7. policy compiler/adapters
   - Codex
   - OpenHands
   - Generic AGENTS.md
8. doctor command
9. GitHub Actions generator/integration
10. independent verifier contract
11. integration tests
12. example repository / fixtures
13. documentation

## Hard constraints

- Never treat model self-assessment as evidence.
- Final gate logic must be deterministic.
- Missing required evidence must fail closed.
- Existing user files must not be silently overwritten.
- Required tests must not be weakened to make CI pass.
- Do not claim a command ran unless it actually ran.
- Do not deploy anything to production.
- Do not access production secrets or databases.
- Any unresolved item must be reported as `UNVERIFIED`.
- Do not declare `DONE` or `PRODUCTION_READY` yourself.

## Verification requirements

At minimum execute:

- clean install
- unit tests
- integration tests
- CLI smoke tests
- lint/typecheck if configured
- security scan if configured

Demonstrate at least:

1. all-pass scenario
2. build-fail scenario
3. test-fail scenario
4. missing-verifier scenario
5. verifier-reject scenario
6. security-threshold-fail scenario

## Final status

Use one of:

- `READY_FOR_VERIFICATION`
- `REPAIR_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `BLOCKED`
- `UNVERIFIED`

## Final report

Return:

- actual repository path
- selected stack and why
- architecture summary
- files created/changed
- commands actually executed
- test summary
- integration scenario results
- security result
- limitations
- remaining risks
- unverified items
- recommended completion state
