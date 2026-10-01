# Security model
Trust boundaries: local reviewed policy and trusted executable PATH; untrusted YAML/JSON documents; local child commands; external verifier reports; CI administrators.
No authentication service or production action executor exists. Human-approval checks classify actions; they never execute them. Unknown actions fail closed.

YAML uses safe loading, duplicate-key rejection, strict types and unknown-field rejection. Repository paths reject absolute paths, parent traversal and symlink components. Evidence outputs live only under .ai/evidence; run logs live under .ai/runs. Writes are atomic; concurrent gate runs use an exclusive lock. Init/compile/CI generation preflight all conflicts, refuse overwrite and permit identical content.

Subprocesses receive argv with shell=False, bounded execution time, capped captured output and a minimal environment. Parent environment values with secret-like names are redacted before persistence. Arbitrary unknown secrets printed by trusted programs cannot be reliably recognized: never run with production secrets. No remote command ingestion or credential API exists.

SHA-256 binds evidence to source, policy and logs, detecting accidental changes and stale evidence. Hashes are NOT signatures: a local writer can forge files or change the tool. Manual verifier import records claimed reviewer identity; v1 cannot authenticate that identity. Git-ignored files are excluded from source hashing. If a configured command reads an ignored application input, changing that input does not invalidate evidence; do not use ignored application files as gate inputs.

Semantic verifier reports use a domain-separated Ed25519 signature. The signed payload includes the stable issuer/key ID, provider/model, report, current run/policy/source binding and digest of the exact VerifierInput, including command evidence. The verifier public key is present in repository policy for local validation; trusted CI must pin its fingerprint in protected external configuration because PRs can alter repository files and policy.

Only the fixed verifier step in the separately protected Buildkite pipeline may receive the Cloudflare Workers AI token and Ed25519 private key. It reads a bounded source snapshot and diff as data; it does not execute PR programs or scripts. Candidate-code mechanical gates stay networkless and receive no verifier credentials. Do not store credentials in pipeline YAML, candidate environment, uploaded reports, or repository files. Use a token scoped to Workers AI only. Missing credentials, invalid model output, provider errors and free-quota exhaustion fail closed without switching to a paid plan.

The selected Workers AI Free allocation is a recurring quota, not a trial; it may change under the provider's terms. Model review is a fallible signal and does not prove code benign. This repository keeps `independent_verification_required: false` until a restricted provider token, signing key and protected verifier step have been configured and live evidence has passed. A green mechanical gate alone is not a semantic review.

Security tests cover traversal, symlinks, malformed/duplicate YAML, type confusion, stale evidence, failed commands, timeout, redaction and forged command records. Bandit scans source; pip-audit scans installed dependency vulnerabilities. Neither proves absence of vulnerabilities.
