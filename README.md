# AI Coding Governance Platform

`aicg` is a local, model-independent governance CLI for AI coding repositories. It compiles canonical policy into agent instructions, runs configured checks, records evidence, and makes deterministic final decisions. Its optional Semantic Verifier calls Cloudflare Workers AI and emits signed, request-bound evidence; it does not deploy production systems.

## Install

Python 3.12+ on macOS or Linux. Mechanical checks require no API. Semantic verification needs a Cloudflare Workers AI account and token; its Free plan currently has a recurring daily allocation and rejects requests after quota instead of billing unless the account is upgraded. [Current pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
aicg --help
```

For distribution, run `python -m build --wheel --no-isolation` and install the resulting wheel. Runtime dependencies are pinned in `requirements.lock`; development and validation dependencies are pinned in `requirements-dev.lock`. The package is not published to a registry by this task.

## Quickstart in another repository

```sh
git init my-project
cd my-project
aicg init
# Edit policy.yaml, PROJECT_SPEC.md and the four .ai documents.
aicg policy validate
aicg compile
aicg doctor
aicg gate run --dry-run
aicg gate run
aicg verifier request > .ai/runs/verifier-input.json
# Or, in a configured trusted environment, run the signed Workers AI verifier.
aicg verifier run
# External verifier imports must be Ed25519-signed and request-bound.
aicg verifier import /outside/repository/verifier-report.json
aicg gate final
```

Initialization intentionally leaves build/test/security commands empty. Validation fails until real commands are configured. This prevents a new repository from passing through empty checks. `init`, `compile` and `ci generate github` permit identical output but refuse conflicting files before writing. Review the diff, move old generated files explicitly, and regenerate when policy changes. No `--force` overwrite mode exists.

`--root /absolute/repository` can appear before the subcommand. `aicg init` works before Git initialization, but evidence execution requires the actual Git repository root.

## Policy and commands

`MASTER_POLICY.md` contains readable rules; `policy.yaml` contains machine-enforced requirements. Strict schemas reject unknown keys, type coercion, duplicate YAML keys, unsupported adapters, invalid paths, negative security thresholds and required empty commands.

Commands can be argv arrays or quoted strings split by `shlex`. Both use `shell=False`: pipes, redirection, substitution, glob expansion and shell environment assignments are not implicit. Put compound tasks in reviewed scripts and configure their argv explicitly. The policy may explicitly name an interpreter; the tool is not a sandbox.

```yaml
commands:
  build: [python, -m, build, --wheel, --no-isolation]
  test: [python, -m, pytest, -q]
  typecheck: [python, -m, mypy, src]
  lint: [python, -m, ruff, check, src]
  security: [python, -m, aicg.security_scan, src]
```

Any configured command is checked, even if its required flag is false. `security.required` defaults to true. A security command must exit successfully and emit exactly one JSON object containing nonnegative integer `critical` and `high` counts on stdout. Missing counts and malformed output fail closed. The bundled adapter runs Bandit; Bandit has no critical severity, so its normalized critical count is zero and HIGH maps to high. Other scanners require a normalization script. Scanner coverage and policy selection remain the maintainer's responsibility.

Commands receive only PATH, locale, temporary-directory, virtual-environment and system-root variables. Other environment variables, including HOME and credentials, are not inherited. Known secret values in the parent environment and common secret assignments are redacted from logs and stored command arguments. Do not place secrets in policy files, source or command arguments. Arbitrary secrets printed by programs cannot be reliably recognized.

Timeout defaults to 300 seconds per command and `max_output_bytes` to 1 MB per stream. Timeout kills the process group. Oversized output is capped and fails the command evidence. A command failure does not prevent other configured checks from producing diagnostic evidence.

## Evidence and completion

Every attempt creates `.ai/runs/<uuid>/manifest.json`, redacted stdout/stderr logs, command JSON and `summary.json`. Current command evidence lives under `.ai/evidence/`. Timestamps, exit codes, executed argv, log hashes and policy/source hashes are recorded.

A new attempt invalidates older evidence immediately. Missing files, stale source/policy, changed executable modes, altered logs, interrupted attempts, failed commands and missing required external evidence reject final completion. Final evaluation uses the same exclusive lock as execution and import. No command-evidence import API exists.

Source binding includes tracked and untracked nonignored files. Generated run/evidence files and `.ai/workflow.json` are excluded. Git-ignored files are outside this snapshot; a gate that reads ignored application inputs cannot detect changes to them. Do not configure completion checks to depend on those inputs. Ignored dependencies/build products also stay outside the snapshot, so pin dependencies and trust the runtime environment. Symlinked source paths and submodules are not supported in v1.

`aicg gate run` reports command execution status. `aicg gate final` additionally checks required external evidence and security thresholds. A successful runner result alone is not completion.

| Final result | Exit code |
| --- | --- |
| PASS | 0 |
| REJECT | 1 |
| Configuration or operation error | 2 |
| HUMAN_REVIEW_REQUIRED | 3 |

Failures take precedence over requests for human review. A model's self-assessment does not satisfy the structured evidence contract.

## Independent verification

`aicg verifier request` exports the requirement, acceptance criteria, architecture/security/testing/invariant documents, command evidence, Git staged/unstaged diff, and a full bounded source snapshot. Clean CI checkouts and untracked files are included. Binary files are base64 encoded; snapshots exceeding 20 MB are rejected rather than silently truncated. Treat this bundle as confidential source material and send it only to an approved reviewer/provider.

Verifier evidence uses `schema_version: 2` and an Ed25519 signature over issuer/key ID, provider/model, report, current run/policy/source hashes, and a digest of the complete request including gate evidence. Unsigned legacy verifier JSON is rejected. Runtime evidence remains `schema_version: 1`. A required verifier policy must configure the trusted issuer, base64 public key, provider and model together. See [verifier/CONTRACT.md](verifier/CONTRACT.md).

The Python `VerifierProvider` Protocol keeps providers pluggable. This v1 ships a Cloudflare Workers AI adapter for `@cf/google/gemma-4-26b-a4b-it`; request/response size, timeout and output schema are bounded. Set `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and base64 `AICG_VERIFIER_PRIVATE_KEY` only in a trusted verifier process. Tests and examples use fixture reports; those never verify this project's readiness.

Signatures authenticate the configured verifier key and exact request, not the correctness of a model's judgment. A local writer can change the CLI or policy. The trust key used by CI must also be pinned in protected external configuration that PRs cannot change. Never expose the provider token or private signing key to PR-controlled programs or artifacts; the review step reads source as data and does not execute it.

## Other commands

- `aicg workflow show` / `aicg workflow transition SPECIFY`: persist and validate workflow transitions. State tracks progress; it cannot replace final evidence checks.
- `aicg approval check production_deploy`: classify an action; never execute it. Unknown actions require review. No production executor exists.
- `aicg doctor`: check Git, policy, required documents/directories, command executables, evidence writability, generated instructions and CI. It does not execute commands or prove their correctness.
- `aicg schema policy|command|external|verifier-input|verifier-attestation`: export JSON Schema.
- `aicg ci generate github`: generate GitHub Actions integration that follows the verifier requirement in `policy.yaml`.

## GitHub Actions

Generated consumer workflows require the repository variable `AICG_INSTALL_SPEC` to point at a trusted immutable wheel URL or pinned package source. No registry release is assumed. Review installation inputs and configure the project's build dependencies before gate execution.

When `independent_verification_required` is true, configure the trust key in protected external CI, then run/import a signed report before `gate final`. Missing or invalid current-request evidence fails closed. When false, the final gate checks configured mechanical requirements only. This repository keeps that setting false until the Cloudflare token, signing key and isolated Buildkite verifier step are configured. Its protected `main` currently requires mechanical GitHub and Buildkite checks with no PR approval. A green run proves configured checks passed, not independent review or production readiness. Never grant secrets to PR-controlled jobs.

This repository runs clean installation, policy validation, all configured gates, example scenarios and dependency audit in GitHub Actions. `policy.yaml` requires build, tests, typecheck, lint, security and runtime validation; it does not yet require a separate verifier. Check the Actions page for current run evidence.

## Validation

```sh
python -m pytest -q
python -m ruff check src tests examples gates
python -m mypy src/aicg
python -m build --wheel --no-isolation
python -m bandit -r src -f json
python -m pip_audit -r requirements.lock --strict --disable-pip --no-deps
python examples/scenarios.py
```

The dependency audit's `--no-deps` mode is used only with the fully resolved lock file; every transitive runtime dependency is present. Tests cover all-pass, build-fail, test-fail, missing/unsigned/tampered verifier, request replay, provider errors and security-threshold-fail. Scanner and signed reports in tests are fixtures, not production scan results.

See [`.ai/agent-swarm-ledger.md`](.ai/agent-swarm-ledger.md) for persistent task assignments and `docs/VALIDATION.md` for the validation procedure and completion boundaries. Generated evidence under `.ai/evidence/` and `.ai/runs/` is gitignored. Protected `main` requires strict GitHub Actions `gate` and Buildkite `buildkite/aicg-trusted-gate/pr` checks, with no PR approvals. The Buildkite App is installed with access limited to this repository. The current Buildkite status is a mechanical execution gate: PR-controlled application and test code run without network access or secrets, so it is not authenticated semantic review and cannot prove code benign. Signed verifier support and a free-tier Cloudflare adapter are implemented, but live Buildkite secret isolation and semantic status have not yet been activated. This repository keeps `independent_verification_required: false` until that setup passes. See [v1 boundaries](.ai/known-issues/v1-boundaries.md). Windows is outside v1 support because locking/process-group handling use POSIX facilities.
