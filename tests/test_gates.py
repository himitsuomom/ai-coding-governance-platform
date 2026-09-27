import json
import sys

import pytest
from conftest import configure, external

from aicg.core import GovernanceError, read_json, write_json
from aicg.evidence import ExternalEvidence
from aicg.gates import execute, final_gate, run_gates, run_lock
from aicg.policy import load_policy
from aicg.verifier import import_evidence, verifier_request


def test_all_pass(repo):
    policy = load_policy(repo)
    run = run_gates(repo, policy)
    assert run["status"] == "PASS"
    external(repo)
    assert final_gate(repo, policy)["status"] == "PASS"
    assert final_gate(repo, policy) == final_gate(repo, policy)
    manifest = read_json(repo, f".ai/runs/{run['run_id']}/manifest.json")
    assert set(manifest["records"]) == {"build", "test", "security"}
    record = read_json(repo, ".ai/evidence/build.json")
    assert record["exit_code"] == 0
    assert record["started_at"] <= record["finished_at"]
    assert "build ran" in (repo / record["artifact_paths"][0]).read_text()


@pytest.mark.parametrize("gate", ["build", "test", "security", "lint", "typecheck"])
def test_failing_command_blocks(repo, gate):
    policy = configure(repo, commands={gate: [sys.executable, "-c", "raise SystemExit(7)"]})
    assert run_gates(repo, policy)["status"] == "REJECT"
    external(repo)
    result = final_gate(repo, policy)
    assert result["status"] == "REJECT"
    assert result["gates"][gate] == "FAIL"
    assert "exit_code=7" in " ".join(result["reasons"])


def test_missing_verifier(repo):
    policy = load_policy(repo)
    run_gates(repo, policy)
    assert final_gate(repo, policy)["gates"]["verifier"] == "FAIL"


@pytest.mark.parametrize("report,expected", [("REPAIR_REQUIRED", "REJECT"),
                                            ("INSUFFICIENT_EVIDENCE", "REJECT"),
                                            ("HUMAN_REVIEW_REQUIRED", "HUMAN_REVIEW_REQUIRED")])
def test_verifier_status(repo, report, expected):
    policy = load_policy(repo)
    run_gates(repo, policy)
    external(repo, report)
    assert final_gate(repo, policy)["status"] == expected


def test_failure_precedes_review(repo):
    policy = configure(repo, commands={"build": [sys.executable, "-c", "exit(1)"]})
    run_gates(repo, policy)
    external(repo, "HUMAN_REVIEW_REQUIRED")
    assert final_gate(repo, policy)["status"] == "REJECT"


@pytest.mark.parametrize("counts", ['{"critical":1,"high":0}', '{"critical":0,"high":1}',
                                    '{}', '{"critical":0,"high":-1}', '{"critical":0,"high":true}', 'not json'])
def test_security_fail_closed(repo, counts):
    policy = configure(repo, commands={"security": [sys.executable, "-c", f"print({counts!r})"]})
    run_gates(repo, policy)
    external(repo)
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_runtime_required(repo):
    policy = configure(repo, completion={"runtime_validation_required": True})
    run_gates(repo, policy)
    external(repo)
    assert final_gate(repo, policy)["status"] == "REJECT"
    external(repo, kind="runtime")
    assert final_gate(repo, policy)["status"] == "PASS"


def test_runtime_runner(repo):
    policy = configure(repo, completion={"runtime_validation_required": True},
                       commands={"runtime": [sys.executable, "-c", "print('runtime')"]})
    run_gates(repo, policy)
    external(repo)
    assert final_gate(repo, policy)["status"] == "PASS"
    with pytest.raises(GovernanceError):
        external(repo, kind="runtime")


def test_dry_run_no_effects(repo):
    policy = configure(repo, commands={"build": [sys.executable, "-c", "open('sentinel','w').write('bad')"]})
    before = sorted(str(p) for p in repo.rglob("*"))
    assert run_gates(repo, policy, True)["dry_run"]
    assert before == sorted(str(p) for p in repo.rglob("*"))


@pytest.mark.parametrize("mutation", ["source", "policy", "log", "record", "delete", "incomplete"])
def test_stale_tampered_missing_rejected(repo, mutation):
    policy = load_policy(repo)
    run = run_gates(repo, policy)
    external(repo)
    if mutation == "source":
        (repo / "new-source.py").write_text("new code")
    elif mutation == "policy":
        policy = configure(repo, timeout_seconds=99)
    elif mutation == "log":
        (repo / f".ai/runs/{run['run_id']}/build.stdout.log").write_text("altered")
    elif mutation == "record":
        record = read_json(repo, ".ai/evidence/build.json")
        record["command"] = ["invented"]
        write_json(repo, ".ai/evidence/build.json", record)
    elif mutation == "delete":
        (repo / ".ai/evidence/test.json").unlink()
    else:
        name = f".ai/runs/{run['run_id']}/manifest.json"
        manifest = read_json(repo, name)
        manifest["status"] = "RUNNING"
        write_json(repo, name, manifest)
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_new_run_invalidates_old_verifier(repo):
    policy = load_policy(repo)
    first = run_gates(repo, policy)
    external(repo)
    second = run_gates(repo, policy)
    assert first["run_id"] != second["run_id"]
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_run_changes_source_invalidates(repo):
    policy = configure(repo, commands={"build": [sys.executable, "-c", "open('new.py','w').write('x')"]})
    assert run_gates(repo, policy)["status"] == "REJECT"
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_concurrent_run_rejected(repo):
    with run_lock(repo), pytest.raises(GovernanceError):
        run_gates(repo, load_policy(repo))


def test_timeout_output_limit_and_missing_executable(repo):
    code, _, _, _ = execute(repo, [sys.executable, "-c", "import time; time.sleep(30)"], 1, 1024)
    assert code == 124
    code, output, _, truncated = execute(repo, [sys.executable, "-c", "print('a'*10000)"], 3, 1024)
    assert code == 0 and truncated and len(output) == 1024
    assert execute(repo, ["/no/such/executable"], 1, 1024)[0] == 127


def test_no_shell_interpretation(repo):
    command = [sys.executable, "-c", "import sys; print(sys.argv[1])", "$(touch sentinel); echo bad"]
    code, output, _, _ = execute(repo, command, 3, 1024)
    assert code == 0 and b"$(touch sentinel)" in output
    assert not (repo / "sentinel").exists()


def test_secret_redaction_and_environment(repo, monkeypatch):
    monkeypatch.setenv("EXAMPLE_API_TOKEN", "test-secret-123456")
    policy = configure(repo, commands={"build": [sys.executable, "-c",
        "import os; print('test-secret-123456'); print(os.getenv('EXAMPLE_API_TOKEN', 'not-inherited'))"]})
    run = run_gates(repo, policy)
    files = list((repo / ".ai/evidence").glob("*.json")) + list((repo / f".ai/runs/{run['run_id']}").glob("*"))
    assert all("test-secret-123456" not in p.read_text() for p in files)
    output = (repo / f".ai/runs/{run['run_id']}/build.stdout.log").read_text()
    assert "[REDACTED]" in output and "not-inherited" in output


def test_self_assessment_invalid(repo):
    policy = load_policy(repo)
    run_gates(repo, policy)
    write_json(repo, ".ai/evidence/verifier.json", {"status": "PASS", "message": "I am done"})
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_external_contract_and_input(repo):
    policy = load_policy(repo)
    run_gates(repo, policy)
    request = verifier_request(repo, policy)
    assert request["original_requirement"] and request["acceptance_criteria"]
    assert set(request["documents"]) == {"ARCHITECTURE", "SECURITY", "TESTING", "INVARIANTS"}
    file = external(repo)
    data = json.loads(file.read_text())
    data["report"]["security_concerns"] = ["unresolved"]
    with pytest.raises(ValueError):
        ExternalEvidence.model_validate(data)
    data["report"]["status"] = "REPAIR_REQUIRED"
    file.write_text(json.dumps(data))
    with pytest.raises(GovernanceError):
        import_evidence(repo, policy, file)
