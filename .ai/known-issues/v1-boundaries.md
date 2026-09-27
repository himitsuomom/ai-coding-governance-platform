# v1 boundaries

- GitHub-hosted Linux execution is UNVERIFIED until the repository is published and its workflow runs.
- Independent reviewer identity is a claimed string, not an authenticated attestation. Protected CI administration is required.
- The runner is not a sandbox; trusted policy commands have the local OS account's file/network access.
- Ignored files and dependencies are not part of source hashing. Pin dependencies and protect the environment.
- Git submodules, symlinked source and Windows execution are unsupported in v1.
- Concurrent hostile filesystem mutations by a local writer cannot be comprehensively prevented by a userspace CLI; hashes and locks defend normal stale/concurrent operation.
- Default initialization intentionally has empty required commands and project-document TODOs. It must reject completion until configured.
