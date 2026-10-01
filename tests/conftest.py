import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aicg.adapters import DOCUMENTS, init_repo
from aicg.evidence import VerifierReport
from aicg.gates import current_context
from aicg.policy import load_policy
from aicg.verifier import MODEL_ID, VerifierInput, import_evidence, sign_verifier_report, verifier_request

TEST_ISSUER = "test://aicg-verifier"
TEST_PROVIDER = "cloudflare-workers-ai"
TEST_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_PUBLIC_KEY = base64.b64encode(TEST_PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def configure(root, **changes):
    data = yaml.safe_load((root / "policy.yaml").read_text())
    for section, values in changes.items():
        if isinstance(values, dict):
            data.setdefault(section, {}).update(values)
        else:
            data[section] = values
    (root / "policy.yaml").write_text(yaml.safe_dump(data))
    return load_policy(root)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    init_repo(root)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "PROJECT_SPEC.md").write_text("# Requirements\nA deterministic CLI.\n")
    for name in DOCUMENTS:
        (root / f".ai/{name}.md").write_text(f"# {name}\nReviewed requirements.\n")
    configure(root, commands={
        "build": [sys.executable, "-c", "print('build ran')"],
        "test": [sys.executable, "-c", "print('test ran')"],
        "security": [sys.executable, "-c", 'print(\'{"critical": 0, "high": 0}\')'],
    }, completion={"independent_verification_required": True},
       verifier={"issuer": TEST_ISSUER, "key": TEST_PUBLIC_KEY,
                 "provider": TEST_PROVIDER, "model": MODEL_ID})
    return root


def external(root: Path, status="PASS", kind="verifier", **changes):
    policy = load_policy(root)
    binding, _ = current_context(root, policy)
    report = {"status": status, "failed_criteria": [], "architecture_concerns": [],
              "security_concerns": [], "missing_evidence": [], "repair_instructions": []}
    if kind == "verifier":
        request = VerifierInput.model_validate(verifier_request(root, policy))
        signed = sign_verifier_report(request, VerifierReport.model_validate(report), TEST_PRIVATE_KEY,
                                      issuer=TEST_ISSUER, provider=TEST_PROVIDER, model=MODEL_ID)
        body = signed.model_dump()
    else:
        body = {**binding, "schema_version": 1, "kind": kind, "producer": "external",
                "reviewer": "TEST FIXTURE ONLY", "recorded_at": "2026-01-01T00:00:00+00:00",
                "report": report}
    body.update(changes)
    file = root.parent / f"{kind}-fixture.json"
    file.write_text(json.dumps(body))
    import_evidence(root, load_policy(root), file)
    return file
