# AI Coding Governance Platform

`aicg` is a local, model-independent governance CLI for AI coding repositories. It compiles canonical policy into agent instructions, runs configured checks, records evidence, and makes deterministic final decisions. It does not call an LLM or deploy production systems.

## Install

Python 3.12+ on macOS or Linux. No paid API is required.

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
# Have an independent reviewer/provider produce a context-bound report.
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

Source binding includes tracked and untracked nonignored files. Generated run/evidence files and `.ai/workflow.json` are excluded. Git-ignored dependencies/build products are outside this snapshot. Pin dependencies and trust the runtime environment. Symlinked source paths and submodules are not supported in v1.

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

External reports require the exact `run_id`, `policy_hash` and `source_hash` from that request. They also contain `schema_version: 1`, `kind: verifier` (or runtime), `producer: external`, `reviewer`, timezone-aware `recorded_at`, and a `report` object. See [verifier/CONTRACT.md](verifier/CONTRACT.md) and exported JSON schemas. Conflicting reports for the same run are refused; start a new run for a new review.

The Python `VerifierProvider` Protocol supports generic LLM or human integrations without choosing a vendor. This v1 ships manual import and the interface, not a commercial provider implementation. Tests and examples use explicitly labeled fixture reports; those never verify this project's readiness.

Hashes detect stale/altered evidence; they are not signatures. A local writer can forge all files or change the CLI. Manual import records a claimed reviewer identity, not authenticated independence. Enforce adversarial separation through protected CI workflows, independent reviewer storage and branch protection. The CLI never claims that mutable local files alone prevent an adversarial agent from bypassing governance.

## Other commands

- `aicg workflow show` / `aicg workflow transition SPECIFY`: persist and validate workflow transitions. State tracks progress; it cannot replace final evidence checks.
- `aicg approval check production_deploy`: classify an action; never execute it. Unknown actions require review. No production executor exists.
- `aicg doctor`: check Git, policy, required documents/directories, command executables, evidence writability, generated instructions and CI. It does not execute commands or prove their correctness.
- `aicg schema policy|command|external|verifier-input`: export JSON Schema.
- `aicg ci generate github`: generate GitHub Actions integration that follows the verifier requirement in `policy.yaml`.

## GitHub Actions

Generated consumer workflows require the repository variable `AICG_INSTALL_SPEC` to point at a trusted immutable wheel URL or pinned package source. No registry release is assumed. Review installation inputs and configure the project's build dependencies before gate execution.

When `independent_verification_required` is true, integrate a trusted verifier after request export and before `gate final`; missing current-run evidence fails closed. When false, the final gate checks configured mechanical requirements only. This repository uses that mode because no trusted reviewer/provider identity is available. Its protected `main` requires the `gate` status and no PR approval. A green run proves configured checks passed, not independent review or production readiness. Never grant secrets to untrusted pull-request jobs. The template runs on pushes and pull requests, uses read-only repository permissions, and uploads evidence with `always()`.

This repository runs clean installation, policy validation, all configured gates, example scenarios and dependency audit in GitHub Actions. `policy.yaml` requires build, tests, typecheck, lint, security and runtime validation; it does not require a separate verifier. Branch protection requires the `gate` check. Check the Actions page for current run evidence.

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

The dependency audit's `--no-deps` mode is used only with the fully resolved lock file; every transitive runtime dependency is present. Six example scenarios run real subprocesses in temporary Git repositories: all-pass, build-fail, test-fail, missing-verifier, verifier-reject and security-threshold-fail. The scanner and reviewer payloads in examples are test fixtures, not production scan results.

See [`.ai/agent-swarm-ledger.md`](.ai/agent-swarm-ledger.md) for persistent task assignments and `docs/VALIDATION.md` for the validation procedure and completion boundaries. Generated evidence under `.ai/evidence/` and `.ai/runs/` is gitignored, so clean clones do not contain local run logs. The Linux-container PASS was recorded only in the original local checkout. The latest post-merge GitHub Actions run for this validation, [36359933283](https://github.com/himitsuomom/ai-coding-governance-platform/actions/runs/36359933283), passed the final gate and all workflow checks. The current public branch API confirms `main` is protected and requires the `gate` status from GitHub Actions; detailed review, admin, force-push and deletion settings were last read back on 2026-09-27. This status check does not make the PR workflow an independent trust anchor; see [v1 boundaries](.ai/known-issues/v1-boundaries.md). Windows is outside v1 support because locking/process-group handling use POSIX facilities.
