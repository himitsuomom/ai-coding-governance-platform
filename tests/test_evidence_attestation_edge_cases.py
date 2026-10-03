import base64
import json

import pytest
from conftest import MODEL_ID, TEST_ISSUER, TEST_PRIVATE_KEY, TEST_PROVIDER

from aicg.core import GovernanceError
from aicg.evidence import VerifierReport, verifier_signing_bytes
from aicg.gates import run_gates
from aicg.policy import load_policy
from aicg.verifier import (
    VerifierInput,
    import_evidence,
    sign_verifier_report,
    verifier_request,
)


def _signed_evidence(repo, tmp_path, *, issuer=TEST_ISSUER, provider=TEST_PROVIDER,
                     model=MODEL_ID):
    policy = load_policy(repo)
    run_gates(repo, policy)
    request = VerifierInput.model_validate(verifier_request(repo, policy))
    report = VerifierReport(status="PASS", failed_criteria=[], architecture_concerns=[],
                            security_concerns=[], missing_evidence=[], repair_instructions=[])
    signed = sign_verifier_report(request, report, TEST_PRIVATE_KEY, issuer=issuer,
                                  provider=provider, model=model)
    path = tmp_path / "attestation.json"
    path.write_text(signed.model_dump_json())
    return policy, path, signed


@pytest.mark.parametrize(
    "signature",
    [
        "%%%not-base64%%%",
        base64.b64encode(b"x" * 63).decode(),
    ],
    ids=["malformed-base64", "wrong-signature-length"],
)
def test_import_rejects_malformed_ed25519_signature(repo, tmp_path, signature):
    policy, path, signed = _signed_evidence(repo, tmp_path)
    payload = signed.model_dump()
    payload["signature"] = signature
    path.write_text(json.dumps(payload))

    with pytest.raises(GovernanceError, match="invalid external evidence"):
        import_evidence(repo, policy, path)


@pytest.mark.parametrize(
    "recorded_at",
    [
        "2026-01-01T00:00:00",
        "2999-01-01T00:00:00+00:00",
    ],
    ids=["naive-timestamp", "future-timestamp"],
)
def test_import_rejects_invalid_timestamp_on_valid_signature(repo, tmp_path, recorded_at):
    policy, path, signed = _signed_evidence(repo, tmp_path)
    payload = signed.model_dump()
    payload["recorded_at"] = recorded_at
    payload["signature"] = base64.b64encode(
        TEST_PRIVATE_KEY.sign(verifier_signing_bytes(payload))
    ).decode()
    path.write_text(json.dumps(payload))

    with pytest.raises(GovernanceError, match="invalid external evidence"):
        import_evidence(repo, policy, path)


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("issuer", "test://untrusted-issuer"),
        ("provider", "untrusted-provider"),
        ("model", "untrusted-model"),
    ],
)
def test_import_rejects_valid_signature_with_unpinned_identity_claim(repo, tmp_path, claim, value):
    claims = {"issuer": TEST_ISSUER, "provider": TEST_PROVIDER, "model": MODEL_ID}
    claims[claim] = value
    policy, path, _ = _signed_evidence(repo, tmp_path, **claims)

    with pytest.raises(GovernanceError, match="issuer/provider/model is not trusted"):
        import_evidence(repo, policy, path)
