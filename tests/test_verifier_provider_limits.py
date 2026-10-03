import pytest

from aicg.core import GovernanceError
from aicg.verifier import (
    MAX_INPUT_BYTES,
    MAX_RESPONSE_BYTES,
    CloudflareWorkersAIProvider,
    VerifierInput,
)


def verifier_request(git_diff: str = "diff") -> VerifierInput:
    return VerifierInput(
        run_id="1" * 32,
        policy_hash="2" * 64,
        source_hash="3" * 64,
        original_requirement="req",
        acceptance_criteria="criteria",
        git_diff=git_diff,
        documents={},
        evidence={},
        source_files=[],
        source_snapshot={},
    )


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.read_sizes: list[int] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self.body[:size]


def test_provider_rejects_request_over_input_limit_before_http(monkeypatch):
    opened = []

    def unexpected_request(*args, **kwargs):
        opened.append((args, kwargs))
        pytest.fail("oversized verifier input must be rejected before HTTP")

    monkeypatch.setattr("aicg.verifier._open_verifier_request", unexpected_request)
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")

    with pytest.raises(GovernanceError, match="request exceeds the Workers AI input limit"):
        provider.verify(verifier_request(git_diff="x" * (MAX_INPUT_BYTES + 1)))

    assert opened == []


def test_provider_rejects_oversized_response_and_reads_only_limit_plus_one(monkeypatch):
    response = FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 64))
    monkeypatch.setattr("aicg.verifier._open_verifier_request", lambda *args, **kwargs: response)
    provider = CloudflareWorkersAIProvider("a" * 32, "token-for-test")

    with pytest.raises(GovernanceError, match="response exceeds the allowed size"):
        provider.verify(verifier_request())

    assert response.read_sizes == [MAX_RESPONSE_BYTES + 1]

