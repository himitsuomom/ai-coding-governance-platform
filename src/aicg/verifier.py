"""Provider-neutral verifier interface and context-bound external import."""

import base64
from pathlib import Path
from typing import Protocol

from aicg.core import GovernanceError, digest, json_bytes, read_json, safe_path, write_json
from aicg.evidence import Context, ExternalEvidence, VerifierReport, git, source_names
from aicg.gates import current_context, evidence_path, run_lock
from aicg.policy import Policy


class VerifierInput(Context):
    original_requirement: str
    acceptance_criteria: str
    git_diff: str
    documents: dict[str, str]
    evidence: dict[str, dict]
    source_files: list[str]
    source_snapshot: dict[str, dict]


class VerifierProvider(Protocol):
    """Providers run independently; callers own credentials and trust decisions."""

    def verify(self, request: VerifierInput) -> VerifierReport: ...


def verifier_request(root: Path, policy: Policy) -> dict:
    with run_lock(root):
        return build_request(root, policy)


def build_request(root: Path, policy: Policy) -> dict:
    binding, _ = current_context(root, policy)
    requirement = safe_path(root, "PROJECT_SPEC.md").read_text()
    documents = {name: safe_path(root, f".ai/{name}.md").read_text()
                 for name in ("ARCHITECTURE", "SECURITY", "TESTING", "INVARIANTS")}
    criteria_path = safe_path(root, ".ai/specs/v1-acceptance.md")
    evidence = {}
    for gate in ("build", "test", "typecheck", "lint", "security", "runtime"):
        name = evidence_path(policy, gate)
        if safe_path(root, name).exists():
            evidence[gate] = read_json(root, name)
    snapshot: dict[str, dict] = {}
    records = []
    total = 0
    for name in source_names(root):
        path = safe_path(root, name)
        if not path.exists():
            snapshot[name] = {"deleted": True}
            records.append([name, "DELETED", 0])
            continue
        total += path.stat().st_size
        if total > 20_000_000:
            raise GovernanceError("source snapshot exceeds 20 MB; use an external repository-aware provider")
        content = path.read_bytes()
        try:
            snapshot[name] = {"encoding": "utf-8", "content": content.decode("utf-8")}
        except UnicodeDecodeError:
            snapshot[name] = {"encoding": "base64", "content": base64.b64encode(content).decode()}
        snapshot[name]["executable_mode"] = path.stat().st_mode & 0o111
        records.append([name, digest(content), snapshot[name]["executable_mode"]])
    if digest(json_bytes(records)) != binding["source_hash"]:
        raise GovernanceError("source changed while assembling verifier snapshot")
    # Include staged/unstaged diffs plus full source for clean CI and untracked files.
    diff = git(root, "diff", "--no-ext-diff").decode(errors="replace")
    diff += git(root, "diff", "--cached", "--no-ext-diff").decode(errors="replace")
    if current_context(root, policy)[0] != binding:
        raise GovernanceError("source changed while assembling verifier request")
    return VerifierInput(**binding, original_requirement=requirement,
                         acceptance_criteria=criteria_path.read_text() if criteria_path.exists() else requirement,
                         git_diff=diff, documents=documents, evidence=evidence,
                         source_files=list(snapshot), source_snapshot=snapshot).model_dump()


def import_evidence(root: Path, policy: Policy, file: Path) -> dict:
    if file.stat().st_size > 4_000_000:
        raise GovernanceError("external evidence too large")
    evidence = ExternalEvidence.model_validate_json(file.read_bytes())
    with run_lock(root):
        binding, _ = current_context(root, policy)
        if any(getattr(evidence, key) != value for key, value in binding.items()):
            raise GovernanceError("external evidence is not for the current source/policy/run")
        name = evidence_path(policy, evidence.kind)
        if evidence.kind == "runtime" and policy.commands.runtime:
            raise GovernanceError("runtime is runner-owned when a runtime command is configured")
        path = safe_path(root, name)
        if path.exists():
            old = read_json(root, name)
            if old.get("run_id") == evidence.run_id and old != evidence.model_dump():
                raise GovernanceError("conflicting external evidence; start a new run for a new review")
        result = evidence.model_dump()
        write_json(root, name, result)
        write_json(root, f".ai/runs/{evidence.run_id}/{evidence.kind}.external.json", result)
        return {"status": "IMPORTED", "kind": evidence.kind, "path": name}
