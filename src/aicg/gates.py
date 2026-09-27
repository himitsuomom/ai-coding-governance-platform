"""Local command runner and deterministic final gate."""

import fcntl
import os
import re
import selectors
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from aicg.core import GovernanceError, digest, read_json, safe_path, write_bytes, write_json
from aicg.evidence import CommandEvidence, Context, Counts, ExternalEvidence, context, now
from aicg.policy import Policy, argv

SECRET_NAME = re.compile(r"SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL", re.IGNORECASE)


def redact(text: str) -> str:
    for key, value in os.environ.items():
        if SECRET_NAME.search(key) and len(value) >= 4:
            text = text.replace(value, "[REDACTED]")
    return re.sub(r"(?i)((?:password|token|secret|api_key)\s*[=:]\s*)[^\s,;]+", r"\1[REDACTED]", text)


def child_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if key in {"PATH", "LANG", "LC_ALL", "TMPDIR", "VIRTUAL_ENV", "SYSTEMROOT"}}


@contextmanager
def run_lock(root: Path):
    path = safe_path(root, ".ai/runs/runner.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GovernanceError("another gate operation is running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def execute(root: Path, command: list[str], timeout: int, limit: int) -> tuple[int, bytes, bytes, bool]:
    """Drain both pipes with bounded memory and kill the entire process group on timeout."""
    buffers = [bytearray(), bytearray()]
    truncated = False
    timed_out = False
    try:
        process = subprocess.Popen(  # nosec B603: explicitly reviewed policy argv, no implicit shell
            command, cwd=root, env=child_environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
    except OSError as exc:
        return 127, b"", str(exc).encode(), False
    deadline = time.monotonic() + timeout
    if process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise GovernanceError("command output pipes unavailable")
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ, 0)
        selector.register(process.stderr, selectors.EVENT_READ, 1)
        while selector.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            for key, _ in selector.select(timeout=0.05):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                target = buffers[key.data]
                remaining = max(0, limit - len(target))
                target.extend(chunk[:remaining])
                truncated |= len(chunk) > remaining
        process.wait()
    if process.stdout:
        process.stdout.close()
    if process.stderr:
        process.stderr.close()
    if timed_out:
        buffers[1].extend(b"\nCommand timed out; process group killed.\n")
    return 124 if timed_out else process.returncode, bytes(buffers[0]), bytes(buffers[1]), truncated


def evidence_path(policy: Policy, gate: str) -> str:
    if gate in {"security", "runtime", "verifier"}:
        return getattr(policy.evidence, f"{gate}_result")
    return f".ai/evidence/{gate}.json"


def plan(policy: Policy) -> dict[str, list[str]]:
    return {name: argv(command) for name, command in policy.commands.model_dump().items() if argv(command)}


def run_gates(root: Path, policy: Policy, dry_run: bool = False) -> dict:
    commands = plan(policy)
    if dry_run:
        return {"dry_run": True, "commands": commands}
    with run_lock(root):
        binding = context(root, policy, uuid4().hex)
        run_dir = f".ai/runs/{binding['run_id']}"
        safe_path(root, run_dir).mkdir()
        manifest = {**binding, "status": "RUNNING", "started_at": now(), "records": {}}
        write_json(root, ".ai/evidence/current.json", binding)
        write_json(root, f"{run_dir}/manifest.json", manifest)
        records = {}
        for gate, command in commands.items():
            started = now()
            exit_code, stdout, stderr, truncated = execute(
                root, command, policy.timeout_seconds, policy.max_output_bytes)
            findings = None
            if gate == "security" and exit_code == 0 and not truncated:
                try:
                    findings = Counts.model_validate_json(stdout)
                except ValueError:
                    exit_code = 65
                    stderr += b"\nSecurity stdout must be JSON with critical/high integer counts.\n"
            logs = {}
            for label, content in (("stdout", stdout), ("stderr", stderr)):
                name = f"{run_dir}/{gate}.{label}.log"
                clean = redact(content.decode(errors="replace")).encode()
                write_bytes(root, name, clean)
                logs[name] = digest(clean)
            record = CommandEvidence.model_validate({
                **binding, "kind": gate, "status": "PASS" if exit_code == 0 and not truncated else "FAIL",
                "command": command, "exit_code": exit_code, "started_at": started, "finished_at": now(),
                "artifact_paths": list(logs), "artifact_hashes": logs, "truncated": truncated,
                "findings": findings.model_dump() if findings else None,
            }).model_dump()
            # Command arguments may contain secrets. Persist only redacted arguments.
            record["command"] = [redact(part) for part in record["command"]]
            name = evidence_path(policy, gate)
            write_json(root, name, record)
            write_json(root, f"{run_dir}/{gate}.json", record)
            manifest["records"][gate] = digest(safe_path(root, name).read_bytes())
            records[gate] = {"status": record["status"], "command": record["command"],
                             "exit_code": exit_code, "evidence_path": name}
            write_json(root, f"{run_dir}/manifest.json", manifest)
        unchanged = context(root, policy, binding["run_id"]) == binding
        manifest.update(status="COMPLETE" if unchanged else "INVALIDATED", finished_at=now())
        write_json(root, f"{run_dir}/manifest.json", manifest)
        result = {**binding, "status": "PASS" if unchanged and all(
            item["status"] == "PASS" for item in records.values()) else "REJECT", "gates": records}
        write_json(root, f"{run_dir}/summary.json", result)
        return result


def current_context(root: Path, policy: Policy) -> tuple[dict, dict]:
    binding = Context.model_validate(read_json(root, ".ai/evidence/current.json")).model_dump()
    if binding != context(root, policy, binding["run_id"]):
        raise GovernanceError("stale evidence: source or policy changed")
    manifest = read_json(root, f".ai/runs/{binding['run_id']}/manifest.json")
    if manifest.get("status") != "COMPLETE" or any(manifest.get(k) != v for k, v in binding.items()):
        raise GovernanceError("incomplete or mismatched run manifest")
    if not isinstance(manifest.get("records"), dict):
        raise GovernanceError("invalid run records")
    return binding, manifest


def check_command(root: Path, policy: Policy, gate: str, binding: dict, manifest: dict) -> dict:
    path = evidence_path(policy, gate)
    evidence = CommandEvidence.model_validate(read_json(root, path))
    if any(getattr(evidence, key) != value for key, value in binding.items()):
        raise GovernanceError("mismatched command context")
    if evidence.kind != gate or evidence.command != [redact(part) for part in argv(getattr(policy.commands, gate))]:
        raise GovernanceError("mismatched command")
    if digest(safe_path(root, path).read_bytes()) != manifest["records"].get(gate):
        raise GovernanceError("command evidence was altered")
    expected_logs = {f".ai/runs/{binding['run_id']}/{gate}.{stream}.log" for stream in ("stdout", "stderr")}
    if set(evidence.artifact_paths) != expected_logs:
        raise GovernanceError("incorrect command log paths")
    for name, expected in evidence.artifact_hashes.items():
        if digest(safe_path(root, name).read_bytes()) != expected:
            raise GovernanceError("command log was altered")
    if evidence.status != "PASS" or evidence.exit_code != 0:
        raise GovernanceError(f"command failed; exit_code={evidence.exit_code}; evidence={path}")
    if gate == "security":
        if evidence.findings is None:
            raise GovernanceError("security counts missing")
        if (evidence.findings.critical > policy.security.max_critical_findings
                or evidence.findings.high > policy.security.max_high_findings):
            raise GovernanceError("security threshold exceeded")
    return evidence.model_dump()


def check_external(root: Path, policy: Policy, gate: str, binding: dict) -> ExternalEvidence:
    evidence = ExternalEvidence.model_validate(read_json(root, evidence_path(policy, gate)))
    if evidence.kind != gate or any(getattr(evidence, key) != value for key, value in binding.items()):
        raise GovernanceError("external evidence context mismatch")
    return evidence


def final_gate(root: Path, policy: Policy) -> dict:
    with run_lock(root):
        return evaluate_final(root, policy)


def evaluate_final(root: Path, policy: Policy) -> dict:
    failures = []
    review = []
    gates = {}
    try:
        binding, manifest = current_context(root, policy)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {"status": "REJECT", "reasons": [f"run: {type(exc).__name__}: {redact(str(exc))}"], "gates": {}}
    for gate, command in policy.commands.model_dump().items():
        required = policy.required_commands().get(gate, policy.completion.runtime_validation_required)
        if not argv(command) and not required:
            gates[gate] = "NOT_REQUIRED"
            continue
        if gate == "runtime" and not argv(command):
            continue
        try:
            check_command(root, policy, gate, binding, manifest)
            gates[gate] = "PASS"
        except (OSError, ValueError, TypeError, KeyError) as exc:
            gates[gate] = "FAIL"
            failures.append(f"{gate}: {redact(str(exc))}")
    external = {"verifier": policy.completion.independent_verification_required,
                "runtime": policy.completion.runtime_validation_required and not argv(policy.commands.runtime)}
    for gate, required in external.items():
        if not required:
            if gate not in gates:
                gates[gate] = "NOT_REQUIRED"
            continue
        try:
            evidence = check_external(root, policy, gate, binding)
            status = evidence.report.status
            gates[gate] = status
            if status == "HUMAN_REVIEW_REQUIRED":
                review.append(f"{gate}: human review required")
            elif status != "PASS":
                failures.append(f"{gate}: {status}")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            gates[gate] = "FAIL"
            failures.append(f"{gate}: missing or invalid evidence ({redact(str(exc))})")
    try:
        if current_context(root, policy)[0] != binding:
            failures.append("run changed during final evaluation")
    except (OSError, ValueError, TypeError, KeyError):
        failures.append("source or run changed during final evaluation")
    return {"status": "REJECT" if failures else "HUMAN_REVIEW_REQUIRED" if review else "PASS",
            "reasons": failures + review, "gates": gates, **binding}


def exit_status(result: dict) -> int:
    return {"PASS": 0, "REJECT": 1, "HUMAN_REVIEW_REQUIRED": 3}.get(result.get("status", ""), 2)
