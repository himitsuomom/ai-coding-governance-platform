import json
import shutil
import subprocess
import sys

import pytest
from conftest import configure, external

from aicg.adapters import compile_policy, doctor, generate_ci, init_repo
from aicg.core import GovernanceError
from aicg.gates import run_gates
from aicg.policy import load_policy


def cli(repo, *args):
    return subprocess.run([sys.executable, "-m", "aicg", "--root", str(repo), *args],
                          capture_output=True, text=True, check=False)


def test_init_idempotence_and_conflict(tmp_path):
    root = tmp_path / "new"
    assert init_repo(root)["created"]
    assert not init_repo(root)["created"]
    (root / "MASTER_POLICY.md").write_text("user content")
    with pytest.raises(GovernanceError):
        init_repo(root)
    assert (root / "MASTER_POLICY.md").read_text() == "user content"


def test_compiler_and_doctor(repo):
    policy = load_policy(repo)
    assert doctor(repo)["status"] == "REJECT"
    result = compile_policy(repo, policy)
    assert len(result["created"]) == 3
    assert not compile_policy(repo, policy)["created"]
    expected = {
        "generated/codex/AGENTS.md": "codex",
        "generated/openhands/INSTRUCTIONS.md": "openhands",
        "generated/generic/AGENTS.md": "generic",
    }
    assert set(result["created"]) == set(expected)
    for file, adapter in expected.items():
        text = (repo / file).read_text()
        assert "GENERATED FILE — DO NOT EDIT DIRECTLY" in text
        assert f"Adapter: {adapter}" in text
        assert "Machine-enforced requirements" in text
    assert doctor(repo)["status"] == "PASS"
    (repo / "MASTER_POLICY.md").write_text("changed master")
    assert doctor(repo)["status"] == "REJECT"
    with pytest.raises(GovernanceError):
        compile_policy(repo, policy)


@pytest.mark.parametrize(("artifact", "directory"), [
    (".ai/ARCHITECTURE.md", False), (".ai/SECURITY.md", False),
    (".ai/TESTING.md", False), (".ai/INVARIANTS.md", False),
    (".ai/specs", True), (".ai/adr", True), (".ai/known-issues", True),
])
def test_doctor_reports_missing_project_memory_artifact(repo, artifact, directory):
    compile_policy(repo, load_policy(repo))
    path = repo / artifact
    if directory:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    else:
        path.unlink()
    result = doctor(repo)
    assert result["status"] == "REJECT"
    assert any(artifact in issue for issue in result["issues"])


@pytest.mark.parametrize(("missing", "issue"), [
    ("git", "Git repository missing"),
    ("docs", "missing/unsafe artifact: PROJECT_SPEC.md"),
    ("command", "command not found: build: /definitely-missing/aicg"),
    ("ci", "CI configuration missing: .github/workflows/aicg.yml"),
])
def test_doctor_reports_missing_readiness_inputs(repo, missing, issue):
    if missing == "git":
        shutil.rmtree(repo / ".git")
    elif missing == "docs":
        (repo / "PROJECT_SPEC.md").unlink()
    elif missing == "command":
        compile_policy(repo, configure(repo, commands={"build": ["/definitely-missing/aicg"]}))
    else:
        (repo / ".github/workflows/aicg.yml").unlink()
    result = doctor(repo)
    assert result["status"] == "REJECT"
    assert issue in result["issues"]


@pytest.mark.parametrize("policy_state", ["missing", "invalid"])
def test_doctor_reports_missing_or_invalid_policy(repo, policy_state):
    policy = repo / "policy.yaml"
    if policy_state == "missing":
        policy.unlink()
    else:
        policy.write_text("invalid: true\n")
    result = doctor(repo)
    assert result["status"] == "REJECT"
    assert any(issue.startswith("policy invalid:") for issue in result["issues"])


@pytest.mark.parametrize("evidence_state", ["missing", "not-directory"])
def test_doctor_reports_unavailable_evidence_directory(repo, evidence_state):
    evidence = repo / ".ai/evidence"
    shutil.rmtree(evidence)
    if evidence_state == "not-directory":
        evidence.write_text("blocks the evidence directory")
    result = doctor(repo)
    assert result["status"] == "REJECT"
    assert any(issue.startswith("evidence not writable:") for issue in result["issues"])


def test_ci(repo):
    generate_ci(repo)
    text = (repo / ".github/workflows/aicg.yml").read_text()
    for command in ("aicg policy validate", "aicg gate run", "aicg gate final"):
        assert command in text
    for action in (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    ):
        assert action in text
    assert "pull_request_target" not in text
    assert "contents: read" in text


def test_cli_exit_codes(repo):
    assert cli(repo, "--help").returncode == 0
    assert cli(repo, "policy", "validate").returncode == 0
    assert cli(repo, "gate", "run", "--dry-run").returncode == 0
    assert cli(repo, "gate", "final").returncode == 1
    assert cli(repo, "approval", "check", "production_deploy").returncode == 3
    run_gates(repo, load_policy(repo))
    external(repo, "HUMAN_REVIEW_REQUIRED")
    assert cli(repo, "gate", "final").returncode == 3
    (repo / "policy.yaml").write_text("invalid: true")
    result = cli(repo, "policy", "validate")
    assert result.returncode == 2
    assert json.loads(result.stderr)["status"] == "ERROR"


def test_cli_dry_run_prints_planned_argv_without_running_it(repo):
    command = [sys.executable, "-c", "open('sentinel','w').write('ran')"]
    configure(repo, commands={"build": command})
    result = cli(repo, "gate", "run", "--dry-run")
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["dry_run"] is True
    assert output["commands"]["build"] == command
    assert not (repo / "sentinel").exists()


@pytest.mark.parametrize("kind", ["policy", "command", "external", "verifier-input"])
def test_schemas(repo, kind):
    result = cli(repo, "schema", kind)
    assert result.returncode == 0
    assert json.loads(result.stdout)["type"] == "object"
