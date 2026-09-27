import json
import sys

import pytest
import yaml
from conftest import configure
from pydantic import ValidationError

from aicg.core import GovernanceError, create_files, relative_path, safe_path, workflow
from aicg.policy import Policy, action_check, load_policy


def test_policy_valid(repo):
    assert load_policy(repo).completion.build_required


@pytest.mark.parametrize("section,key,value", [
    ("completion", "build_required", "false"),
    ("completion", "build_required", 1),
    ("completion", "unknown", True),
    ("security", "max_high_findings", -1),
    ("security", "max_high_findings", True),
    ("security", "allow_force_push", True),
    ("commands", "build", ""),
    ("commands", "build", [sys.executable, 5]),
    ("commands", "build", '"unterminated'),
    ("evidence", "verifier_result", "../escape.json"),
    ("evidence", "verifier_result", "/tmp/escape.json"),
    ("evidence", "verifier_result", ".ai/evidence/current.json"),
    ("evidence", "verifier_result", ".ai/evidence/security.json"),
])
def test_invalid_policy(repo, section, key, value):
    with pytest.raises((ValidationError, GovernanceError)):
        configure(repo, **{section: {key: value}})


@pytest.mark.parametrize("mutation", [lambda p: p.pop("completion"),
                                     lambda p: p.update(adapters=["unsupported"]),
                                     lambda p: p.update(adapters=[]),
                                     lambda p: p.update(timeout_seconds=0)])
def test_required_policy_fields(repo, mutation):
    data = load_policy(repo).model_dump()
    mutation(data)
    with pytest.raises(ValueError):
        Policy.model_validate(data)


@pytest.mark.parametrize("text", ["version: 1\nversion: 1\n", "x: [", "!!python/object/apply:os.system ['exit 0']"])
def test_unsafe_yaml(repo, text):
    (repo / "policy.yaml").write_text(text)
    with pytest.raises((GovernanceError, ValueError, yaml.YAMLError)):
        load_policy(repo)


@pytest.mark.parametrize("path", ["", "..", "../x", "/x", "a/../x", "a//b", "./a", "a\\b", "C:/x", "."])
def test_paths_rejected(path):
    with pytest.raises(GovernanceError):
        relative_path(path)


def test_symlink_rejected(repo, tmp_path):
    (repo / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(GovernanceError):
        safe_path(repo, "escape/secret")


def test_all_conflicts_preflight(repo):
    (repo / "existing").write_text("user")
    with pytest.raises(GovernanceError):
        create_files(repo, {"new": b"new", "existing": b"replacement"})
    assert not (repo / "new").exists()
    assert (repo / "existing").read_text() == "user"


def test_workflow(repo):
    assert workflow(repo) == {"state": "DISCOVER"}
    with pytest.raises(GovernanceError):
        workflow(repo, "SUBMIT")
    for state in ("SPECIFY", "ARCHITECT", "IMPLEMENT", "BUILD", "REPAIR", "BUILD", "TEST", "VERIFY", "SUBMIT"):
        assert workflow(repo, state)["state"] == state
    assert json.loads((repo / ".ai/workflow.json").read_text())["state"] == "SUBMIT"


@pytest.mark.parametrize("action", ["production_deploy", "destructive_migration", "auth_boundary_change",
                                  "disable_required_gate", "production_secret_access", "unknown"])
def test_protected_actions(repo, action):
    assert action_check(load_policy(repo), action)["status"] == "HUMAN_REVIEW_REQUIRED"
