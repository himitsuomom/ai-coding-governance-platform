# v1 requirements and acceptance map
Functional scope: FR-001–016 from PROJECT_SPEC.md, including init, compiler, strict policy validation, workflow, runner, evidence, independent verifier contract/import, deterministic final gate, action approval, doctor, dry-run, audit and GitHub generation.
Nonfunctional scope: deterministic decisions; safe paths and command boundaries; minimal dependencies; macOS/Linux; actionable JSON output; local validation without network or model calls.

AC-001 init: generate required artifacts and preserve conflicting files.
AC-002 validate: reject missing fields, wrong types, duplicate keys, unsupported adapters and command contradictions.
AC-003 compile: generate Codex, OpenHands and generic marked instructions; detect stale output.
AC-004/005 failures: nonzero build/test exits block final gate.
AC-006/007 verification: missing or rejected independent report blocks completion.
AC-008 security: absent counts, scanner failure or threshold excess blocks completion.
AC-009 runtime: missing required runtime evidence blocks completion.
AC-010 approval: protected or unknown action requires human review.
AC-011 self-assessment: arbitrary text cannot substitute for structured, context-bound evidence.
AC-012 audit: logs, timestamps, exit codes, manifest and summary are persisted per run.
AC-013 doctor: diagnose missing Git/policy/docs/commands/writable evidence/compiled output/CI.
AC-014 dry-run: show argv without side effects.
AC-015 CI: generate real checkout/install/validation/run/final workflow and artifact upload. Execution on GitHub is separately reported.

Failure cases: interrupted run, concurrent run, malformed evidence, source or policy change after run, path escape, symlink, output overflow, timeout, missing executable, contradictory PASS verifier report and altered logs.
