# Codex + Warp: evidence-first development workflow

This is an **operator runbook**, not a new implementation of the governance gate. Keep `policy.yaml`, `MASTER_POLICY.md`, `AGENTS.md`, and the `.ai/` specifications authoritative. Use this workflow with a repository configured for the existing `aicg` CLI; do not copy a green test report from another repository as proof.

## Boundaries

| Component | Responsibility | Not evidence of completion |
| --- | --- | --- |
| Planner / spec author | Acceptance criteria, risks, scope, failure cases | A plan or an AI judgment |
| Codex in Warp terminal, or Warp Agent | Implement on a dedicated feature branch; run local commands | Agent self-review or screenshots |
| Independent reviewer | Inspect changed files, tests, threat model and residual risks; request repair | A reviewer's free-text `PASS` alone |
| `aicg` CLI | Execute configured checks; bind results to current source/policy/run | `gate run` alone |
| Protected CI / trusted verifier | Enforce required checks and external evidence under protected configuration | An unprotected PR-controlled workflow |

**Warp terminal, Warp Agent and Warp Factory are distinct.** Codex can be run *in* the Warp terminal without using Warp Factory. A ChatGPT subscription can fund eligible Warp Agent model inference after account linking and explicit model selection, but it does not fund cloud runs. On some business plans local platform charges can still apply. Never silently switch to Warp credits, an Auto model, a paid provider, or Factory execution. Verify eligibility/charges in the current Warp account before making requests.

## One change, one handoff

1. **Discover and specify.** The planner identifies the target repository and base revision, writes acceptance criteria and negative cases, and flags authentication, deployment, migration and secret-handling risks.
2. **Branch and implement.** The implementer uses a feature branch or isolated worktree, reads the repository's existing `AGENTS.md` and policy, and does not weaken tests, security thresholds, or approval requirements to get green. Do not run paid cloud agents for this workflow by default.
3. **Run objective checks.** In a configured project environment with `aicg` installed, run the following **in order**. Treat any failure or missing prerequisite as a blocker, not success:

   ```sh
   aicg policy validate
   aicg compile
   aicg doctor
   aicg gate run --dry-run
   aicg gate run
   aicg gate final
   ```

   For a new repository, `aicg init` only scaffolds files; project-specific build, test, typecheck, lint, security and runtime commands must be configured first. Review generated file changes before committing. `gate run` is execution evidence; `gate final` is the deterministic local decision. A successful local decision does **not** by itself establish that remote branch-protection rules are active.
4. **Independent review.** A different reviewer inspects the base-to-head diff, acceptance criteria, negative tests, dependency changes, security implications, and referenced run evidence. For required authenticated verification, accept only signed, current-request-bound attestations from the configured trusted issuer; a reviewer comment is never a substitute.
5. **Submit with traceable evidence.** Open a PR, use the evidence checklist, cite exact checks and run/commit IDs, and separate **passed**, **failed**, **not run**, and **not applicable**. Avoid reporting `DONE` or `PRODUCTION_READY` on agent judgment.
6. **Protected merge only.** Merge is a human decision after actual required GitHub status checks have passed, the expected source App is enforced, and applicable approvals are present. Neither the implementer nor reviewer bypasses a required gate.

## Handoff minimum

Record: target repo, base/head commit, objective/acceptance criteria, changed files, `policy.yaml` revision, commands actually executed, `gate run` and `gate final` outcomes, CI URLs, independent reviewer identity/concerns, blocked or unverified items, and next action. Never include API tokens, secrets, raw credentials or private verifier signing material in prompts, comments or public artifacts.

## Failure and cost safety

- Missing tools, stale evidence, nonzero commands, unverified security controls, absent independent attestation when required, or unavailable trusted CI **fail closed**. Explicitly label the state `BLOCKED`, `REPAIR_REQUIRED`, or `UNVERIFIED` according to the repository's reporting convention.
- Do not authorize paid Warp Factory runs, checkout, cloud inference fallback, production changes, or destructive operations implicitly. Browser OAuth and paid-service enrollment require their own user action.
- A successful Buildkite status is not proof that the exact PR status is *required* by protected `main`. Verify the live protection configuration as an administrator before relying on it.

## References

- Project policy and commands: [README](../README.md), [validation procedure](VALIDATION.md), [authenticated verifier design](ADR-0002-authenticated-semantic-verifier.md).
- Warp's official [ChatGPT subscription connection](https://docs.warp.dev/agents/inference/chatgpt-subscription/) and [Agent overview](https://docs.warp.dev/agents/).
