# Validation procedure and completion boundaries

Run installation, unit/integration/CLI/security regression tests, lint, typecheck, real Bandit scan, dependency audit and wheel installation before requesting independent verification. `examples/scenarios.py` separately demonstrates the six mandatory final-gate scenarios with explicitly labeled test-only reviewer/scanner fixtures.

The authoritative local run is `.ai/evidence/current.json`; its UUID selects the command manifest, logs and summary under `.ai/runs/`. Tests include invalid configuration, rejected paths/symlinks, nonzero processes, missing/failed evidence, security counts, runtime requirements, secret redaction, timeout, bounded output, stale source/modes and concurrency.

A separate agent performed read-only review and reproduced defects independently. Its findings were repaired and covered by regression tests. Review narratives alone are not imported as a PASS report. Actual current-run verifier evidence is a separate artifact.

GitHub Actions run [36310852688](https://github.com/himitsuomom/ai-coding-governance-platform/actions/runs/36310852688) on 2026-09-27 passed clean dependency installation, policy validation, all six configured gates, all six example scenarios, and the dependency audit on Ubuntu/Python 3.12. Its final gate rejected because `.ai/evidence/verifier.json` was absent for that run, as required by fail-closed policy. The run uploaded its evidence artifact.

Pending external verification: trusted verifier integration, protected branch enforcement, authenticated reviewer identity and any production deployment suitability. No production deployment, secrets access or database action was performed. The local tool is not a sandbox or a tamper-proof attestation service.

Policy/security references consulted: Python subprocess documentation (https://docs.python.org/3/library/subprocess.html) for argv, env and timeout semantics; Pydantic strict-mode documentation (https://pydantic.dev/docs/validation/latest/concepts/strict_mode/) for input validation. Exact behavior is covered by tests, including Literal bool/int edge cases.
