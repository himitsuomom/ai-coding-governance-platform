# Invariants
1. Missing, invalid, stale or mismatched required evidence never yields PASS.
2. PASS requires successful exit codes, integrity-checked logs, required security counts, and independent verifier approval when required.
3. A new attempt invalidates previous evidence before commands start; an interrupted run cannot reuse old success.
4. Invalid policy never executes commands. Dry-run never writes state or starts child commands.
5. No implicit shell evaluation. Only explicitly configured commands execute.
6. Paths never escape the repository or traverse symlinks. Generated files never silently overwrite different content.
7. Evidence contains no indiscriminate environment dump. Known secret values are redacted.
8. Failed required checks take precedence over human review. Review cannot override a failure.
9. Illegal workflow transitions are rejected. A final gate result is distinct from model self-assessment.
10. Local evidence integrity is not cryptographic attestation of reviewer independence. CI administration remains a separate trust boundary.
