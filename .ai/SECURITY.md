# Security model
Trust boundaries: local reviewed policy and trusted executable PATH; untrusted YAML/JSON documents; local child commands; external verifier reports; CI administrators.
No authentication service or production action executor exists. Human-approval checks classify actions; they never execute them. Unknown actions fail closed.

YAML uses safe loading, duplicate-key rejection, strict types and unknown-field rejection. Repository paths reject absolute paths, parent traversal and symlink components. Evidence outputs live only under .ai/evidence; run logs live under .ai/runs. Writes are atomic; concurrent gate runs use an exclusive lock. Init/compile/CI generation preflight all conflicts, refuse overwrite and permit identical content.

Subprocesses receive argv with shell=False, bounded execution time, capped captured output and a minimal environment. Parent environment values with secret-like names are redacted before persistence. Arbitrary unknown secrets printed by trusted programs cannot be reliably recognized: never run with production secrets. No remote command ingestion or credential API exists.

SHA-256 binds evidence to source, policy and logs, detecting accidental changes and stale evidence. Hashes are NOT signatures: a local writer can forge files or change the tool. Manual verifier import records claimed reviewer identity; v1 cannot authenticate that identity. Git-ignored files are excluded from source hashing. If a configured command reads an ignored application input, changing that input does not invalidate evidence; do not use ignored application files as gate inputs.

This repository sets `independent_verification_required: false` because no trusted reviewer or provider identity is available. CI still requires configured build, test, typecheck, lint, security and runtime checks. A passing result means those mechanical gates passed; it does not mean an independent review or production-readiness assessment occurred. Enable independent verification before relying on it as a trust boundary.

Security tests cover traversal, symlinks, malformed/duplicate YAML, type confusion, stale evidence, failed commands, timeout, redaction and forged command records. Bandit scans source; pip-audit scans installed dependency vulnerabilities. Neither proves absence of vulnerabilities.
