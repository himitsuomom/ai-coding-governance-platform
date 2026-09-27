import json
import subprocess
import sys

import pytest
from conftest import external

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
    for file in result["created"]:
        assert "GENERATED FILE — DO NOT EDIT DIRECTLY" in (repo / file).read_text()
    assert doctor(repo)["status"] == "PASS"
    (repo / "MASTER_POLICY.md").write_text("changed master")
    assert doctor(repo)["status"] == "REJECT"
    with pytest.raises(GovernanceError):
        compile_policy(repo, policy)


def test_ci(repo):
    generate_ci(repo)
    text = (repo / ".github/workflows/aicg.yml").read_text()
    for command in ("aicg policy validate", "aicg gate run", "aicg gate final"):
        assert command in text
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


@pytest.mark.parametrize("kind", ["policy", "command", "external", "verifier-input"])
def test_schemas(repo, kind):
    result = cli(repo, "schema", kind)
    assert result.returncode == 0
    assert json.loads(result.stdout)["type"] == "object"
