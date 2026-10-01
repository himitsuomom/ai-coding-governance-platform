import base64
import io
import json
from urllib.error import HTTPError

import pytest
from conftest import MODEL_ID, TEST_ISSUER, TEST_PROVIDER, configure, external
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aicg.core import GovernanceError, read_json, write_json
from aicg.evidence import VerifierReport
from aicg.gates import final_gate, run_gates
from aicg.policy import load_policy
from aicg.verifier import (
    CloudflareWorkersAIProvider,
    VerifierInput,
    _RejectVerifierRedirect,
    import_evidence,
    run_verifier,
    sign_verifier_report,
)


def request() -> VerifierInput:
    return VerifierInput(run_id="1" * 32, policy_hash="2" * 64, source_hash="3" * 64,
                         original_requirement="req", acceptance_criteria="criteria", git_diff="diff",
                         documents={}, evidence={}, source_files=[], source_snapshot={})


def report(status="PASS") -> VerifierReport:
    return VerifierReport(status=status, failed_criteria=[], architecture_concerns=[],
                          security_concerns=[], missing_evidence=[], repair_instructions=[])


def test_unsigned_verifier_pass_rejected(repo, tmp_path):
    policy = load_policy(repo)
    run_gates(repo, policy)
    binding = read_json(repo, ".ai/evidence/current.json")
    unsigned = {**binding, "schema_version": 1, "kind": "verifier", "producer": "external",
                "reviewer": "not authenticated", "recorded_at": "2026-01-01T00:00:00+00:00",
                "report": report().model_dump()}
    evidence = tmp_path / "unsigned.json"
    evidence.write_text(json.dumps(unsigned))
    with pytest.raises(GovernanceError, match="invalid external evidence"):
        import_evidence(repo, policy, evidence)
    assert final_gate(repo, policy)["gates"]["verifier"] == "FAIL"


def test_tampered_signed_report_rejected(repo):
    policy = load_policy(repo)
    run_gates(repo, policy)
    evidence = external(repo)
    data = json.loads(evidence.read_text())
    data["report"]["status"] = "REPAIR_REQUIRED"
    evidence.write_text(json.dumps(data))
    with pytest.raises(GovernanceError, match="signature is invalid"):
        import_evidence(repo, policy, evidence)


def test_unknown_signing_key_rejected(repo, tmp_path):
    policy = load_policy(repo)
    run_gates(repo, policy)
    binding = read_json(repo, ".ai/evidence/current.json")
    from aicg.verifier import verifier_request as create_request

    verifier_request = VerifierInput.model_validate(create_request(repo, policy))
    other = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    signed = sign_verifier_report(verifier_request, report(), other, issuer=TEST_ISSUER,
                                  provider=TEST_PROVIDER, model=MODEL_ID)
    evidence = tmp_path / "unknown-key.json"
    evidence.write_text(signed.model_dump_json())
    with pytest.raises(GovernanceError, match="unknown verifier signing key"):
        import_evidence(repo, policy, evidence)
    assert binding["run_id"] == signed.run_id


def test_attestation_replay_after_gate_evidence_change_rejected(repo, tmp_path):
    policy = load_policy(repo)
    run_gates(repo, policy)
    evidence = external(repo)
    command_record = read_json(repo, ".ai/evidence/test.json")
    command_record["command"].append("changed")
    write_json(repo, ".ai/evidence/test.json", command_record)
    with pytest.raises(GovernanceError, match="different request"):
        import_evidence(repo, policy, evidence)


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.body[:size]


def test_cloudflare_provider_parses_valid_report(monkeypatch):
    body = json.dumps({"success": True, "result": {"response": report().model_dump_json()}}).encode()
    def fake_urlopen(http_request, timeout):
        assert http_request.get_header("Authorization") == "Bearer token-for-test"
        assert "@cf/google/gemma-4-26b-a4b-it" in http_request.full_url
        assert json.loads(http_request.data)["max_completion_tokens"] == 2048
        assert timeout == 120
        return Response(body)

    monkeypatch.setattr("aicg.verifier._open_verifier_request", fake_urlopen)
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")
    assert provider.verify(request()).status == "PASS"


@pytest.mark.parametrize("body", [b"not-json", b'{"success":false}',
                                   b'{"success":true,"result":{"response":"not a report"}}'])
def test_cloudflare_provider_rejects_bad_responses(monkeypatch, body):
    monkeypatch.setattr("aicg.verifier._open_verifier_request", lambda *args, **kwargs: Response(body))
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")
    with pytest.raises(GovernanceError):
        provider.verify(request())


def test_cloudflare_provider_fails_closed_on_quota_error(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError("https://api.cloudflare.com", 429, "quota", {}, io.BytesIO(b"quota"))

    monkeypatch.setattr("aicg.verifier._open_verifier_request", fail)
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")
    with pytest.raises(GovernanceError, match="free quota"):
        provider.verify(request())


def test_cloudflare_redirect_is_not_followed(monkeypatch):
    opened = []
    handlers = []

    class RedirectResponse:
        def open(self, http_request, timeout):
            opened.append(http_request.full_url)
            assert handlers[0].redirect_request(http_request, io.BytesIO(), 302, "Found", {},
                                                "https://attacker.example/collect") is None
            raise HTTPError(http_request.full_url, 302, "Found", {}, io.BytesIO())

    def build_redirect_opener(received):
        assert isinstance(received, _RejectVerifierRedirect)
        handlers.append(received)
        return RedirectResponse()

    monkeypatch.setattr("aicg.verifier.build_opener", build_redirect_opener)
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")
    with pytest.raises(GovernanceError):
        provider.verify(request())
    assert len(opened) == 1
    assert opened[0].startswith("https://api.cloudflare.com/")


def test_mismatched_signing_key_is_rejected_before_provider_call(repo, monkeypatch):
    policy = load_policy(repo)
    run_gates(repo, policy)
    other_key = bytes(reversed(range(32)))
    monkeypatch.setenv("AICG_VERIFIER_PRIVATE_KEY", base64.b64encode(other_key).decode())
    monkeypatch.setattr("aicg.verifier.CloudflareWorkersAIProvider.from_environment",
                        lambda: pytest.fail("provider must not be called for an untrusted key"))
    with pytest.raises(GovernanceError, match="does not match the configured verifier key"):
        run_verifier(repo, policy)


def test_required_verifier_needs_complete_trust(repo):
    with pytest.raises(ValueError, match="trusted verifier issuer"):
        configure(repo, completion={"independent_verification_required": True},
                  verifier={"issuer": None, "key": None, "provider": None, "model": None})
