# Testing strategy
Unit: policy strict validation, workflow transitions, source/path safety, final status precedence and verifier contract.
Integration: real subprocesses in temporary Git repositories, init idempotence/conflict, three instruction adapters, command failure, missing/rejecting verifier, security thresholds, runtime requirements, stale/tampered evidence and human approval.
CLI: help, configuration exit 2, rejection exit 1, review exit 3, dry-run no writes/commands, doctor readiness, generated CI.
Required examples: all-pass, build-fail, test-fail, missing-verifier, verifier-reject and security-threshold-fail. Example verifier evidence is explicitly test-only.
Build a wheel, install it in a separate clean virtual environment and run the installed CLI. Run pytest, ruff, mypy, Bandit and pip-audit. GitHub execution remains UNVERIFIED until actually run on GitHub. Implementation-agent assertions never substitute for external verifier evidence.
