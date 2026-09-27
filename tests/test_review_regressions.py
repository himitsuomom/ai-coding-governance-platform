
import pytest
from conftest import configure, external

from aicg.core import GovernanceError
from aicg.evidence import ExternalEvidence, source_hash
from aicg.gates import final_gate, run_gates, run_lock
from aicg.policy import Policy, load_policy
from aicg.verifier import verifier_request


def test_mode_change_invalidates(repo):
    script = repo / "build.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    policy = configure(repo, commands={"build": ["./build.sh"]})
    run_gates(repo, policy)
    external(repo)
    previous = source_hash(repo)
    script.chmod(0o644)
    assert previous != source_hash(repo)
    assert final_gate(repo, policy)["status"] == "REJECT"


def test_verifier_includes_untracked_and_binary_source(repo):
    (repo / "new.py").write_text("print('implementation')")
    (repo / "image.bin").write_bytes(b"\xff\x00")
    policy = load_policy(repo)
    run_gates(repo, policy)
    request = verifier_request(repo, policy)
    assert request["git_diff"] == ""
    assert request["source_snapshot"]["new.py"]["content"] == "print('implementation')"
    assert request["source_snapshot"]["image.bin"]["encoding"] == "base64"


def test_final_cannot_overlap_runner(repo):
    policy = load_policy(repo)
    run_gates(repo, policy)
    external(repo)
    with run_lock(repo), pytest.raises(GovernanceError, match="another gate"):
        final_gate(repo, policy)


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_literal_version_types(repo, value):
    data = load_policy(repo).model_dump()
    data["version"] = value
    with pytest.raises(ValueError):
        Policy.model_validate(data)


def test_literal_security_flag_and_evidence_version(repo):
    data = load_policy(repo).model_dump()
    data["security"]["allow_force_push"] = 0
    with pytest.raises(ValueError):
        Policy.model_validate(data)
    run_gates(repo, load_policy(repo))
    file = external(repo)
    import json
    evidence = json.loads(file.read_text())
    evidence["schema_version"] = True
    with pytest.raises(ValueError):
        ExternalEvidence.model_validate(evidence)


@pytest.mark.parametrize("path", [".ai/evidence/build.json/security.json",
                                ".ai/evidence/verifier.json/security.json"])
def test_ancestor_evidence_paths_rejected(repo, path):
    with pytest.raises(ValueError):
        configure(repo, evidence={"security_result": path})


def test_source_change_during_verifier_request_rejected(repo, monkeypatch):
    from aicg import verifier
    file = repo / "code.py"
    file.write_text("original")
    policy = load_policy(repo)
    run_gates(repo, policy)
    original = verifier.current_context

    def edit_after_context(*args):
        result = original(*args)
        file.write_text("changed after context check")
        return result

    monkeypatch.setattr(verifier, "current_context", edit_after_context)
    with pytest.raises(GovernanceError, match="source changed"):
        verifier_request(repo, policy)
