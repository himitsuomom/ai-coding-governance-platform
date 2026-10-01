"""Evidence schemas and current-source binding."""

import base64
import binascii
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from aicg.core import GovernanceError, digest, json_bytes, safe_path
from aicg.policy import Policy, StrictModel


def now() -> str:
    return datetime.now(UTC).isoformat()


class Context(StrictModel):
    run_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    policy_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Counts(StrictModel):
    critical: int = Field(ge=0)
    high: int = Field(ge=0)


class CommandEvidence(Context):
    schema_version: Literal[1] = 1
    kind: Literal["build", "test", "typecheck", "lint", "security", "runtime"]
    producer: Literal["runner"] = "runner"
    status: Literal["PASS", "FAIL"]
    command: list[str]
    exit_code: int
    started_at: str
    finished_at: str
    artifact_paths: list[str]
    artifact_hashes: dict[str, str]
    truncated: bool = False
    findings: Counts | None = None

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "PASS" and (self.exit_code != 0 or self.truncated):
            raise GovernanceError("inconsistent successful command evidence")
        if datetime.fromisoformat(self.finished_at) < datetime.fromisoformat(self.started_at):
            raise GovernanceError("invalid command timestamps")
        if not self.artifact_paths or set(self.artifact_paths) != set(self.artifact_hashes):
            raise GovernanceError("missing log hashes")
        return self


class VerifierReport(StrictModel):
    status: Literal["PASS", "REPAIR_REQUIRED", "HUMAN_REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"]
    failed_criteria: list[str]
    architecture_concerns: list[str]
    security_concerns: list[str]
    missing_evidence: list[str]
    repair_instructions: list[str]

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "PASS" and any(value for key, value in self.model_dump().items() if key != "status"):
            raise GovernanceError("PASS verifier report contains unresolved concerns")
        return self


class ExternalEvidence(Context):
    schema_version: Literal[1] = 1
    kind: Literal["runtime"]
    producer: Literal["external"] = "external"
    reviewer: str = Field(min_length=1, max_length=200)
    recorded_at: str
    report: VerifierReport

    @model_validator(mode="after")
    def timestamp(self):
        value = datetime.fromisoformat(self.recorded_at)
        if value.tzinfo is None or value > datetime.now(UTC):
            raise GovernanceError("external timestamp must be timezone-aware and not in the future")
        if not self.reviewer.strip():
            raise GovernanceError("reviewer required")
        return self


class VerifierAttestation(Context):
    schema_version: Literal[2] = 2
    kind: Literal["verifier"] = "verifier"
    producer: Literal["aicg-signed-verifier"] = "aicg-signed-verifier"
    issuer: str = Field(min_length=1, max_length=200)
    key_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    recorded_at: str
    report: VerifierReport
    signature: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def valid_signature(self):
        value = datetime.fromisoformat(self.recorded_at)
        if value.tzinfo is None or value > datetime.now(UTC):
            raise GovernanceError("verifier timestamp must be timezone-aware and not in the future")
        try:
            signature = base64.b64decode(self.signature, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise GovernanceError("verifier signature must be base64 Ed25519 bytes") from exc
        if len(signature) != 64:
            raise GovernanceError("verifier signature must be 64 Ed25519 bytes")
        return self


def verifier_signing_bytes(payload: dict) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return b"aicg-verifier-attestation-v2\0" + json_bytes(unsigned)


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)  # nosec B603 B607
    if result.returncode:
        raise GovernanceError("Git repository required")
    return result.stdout


def source_names(root: Path) -> list[str]:
    top = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != root.resolve():
        raise GovernanceError("--root must be the Git repository root")
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\x00")
    return [name for name in sorted(set(names) - {""})
            if not name.startswith((".ai/evidence/", ".ai/runs/")) and name != ".ai/workflow.json"]


def source_hash(root: Path) -> str:
    records = []
    for name in source_names(root):
        path = safe_path(root, name)
        if path.is_dir():
            raise GovernanceError("submodules/directories in source snapshot are unsupported")
        records.append([name, digest(path.read_bytes()) if path.exists() else "DELETED",
                        path.stat().st_mode & 0o111 if path.exists() else 0])
    return digest(json_bytes(records))


def context(root: Path, policy: Policy, run_id: str) -> dict:
    return {"run_id": run_id, "policy_hash": digest(json_bytes(policy.model_dump())),
            "source_hash": source_hash(root)}
