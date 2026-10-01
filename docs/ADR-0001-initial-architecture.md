# ADR-0001: local Python CLI with deterministic evidence gates
Status: accepted for v1.
Use Python 3.12+, argparse, Pydantic 2, PyYAML and setuptools. Python supports the target macOS/Linux platforms; argparse avoids a CLI dependency. Pydantic rejects coercion/unknown fields and exports schemas. PyYAML supports the specified policy format. Development tools are pytest, ruff, mypy, build, Bandit and pip-audit.

Choose a small layered package, not a distributed orchestrator. Strings are parsed with shlex into argv; shell operators are not interpreted. Script files are the portable way to combine steps. Security scanners emit normalized JSON with nonnegative critical/high counts. A bundled Bandit adapter supplies that format.

Evidence is local JSON plus hashed logs and source fingerprints. Manual verifier import and a Python Protocol support independent providers without commercial credentials. No verifier credentials or model provider is bundled. Source fingerprints use Git tracked and untracked nonignored files, excluding .ai/evidence, .ai/runs and workflow state. Ignored files are outside the source snapshot; dependencies must be pinned separately.

The source template directory was nonempty. Implementation uses sibling ai-coding-governance-platform-v1 without overwriting the template. CI remote execution and genuine human verification cannot be claimed from local test fixtures.

See [ADR-0002](ADR-0002-authenticated-semantic-verifier.md) for the authenticated semantic-verifier extension.
