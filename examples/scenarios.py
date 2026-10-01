"""Exercise six integration scenarios. All verifier/scanner reports here are TEST FIXTURES."""

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aicg.adapters import init_repo
from aicg.evidence import VerifierReport
from aicg.verifier import VerifierInput, sign_verifier_report

FIXTURE_ISSUER = "aicg-example-fixture"
FIXTURE_PROVIDER = "offline-test-fixture"
FIXTURE_MODEL = "fixture-only"
FIXTURE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
FIXTURE_PUBLIC_KEY = base64.b64encode(FIXTURE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)).decode()


def cli(root, *args):
    result = subprocess.run([sys.executable, "-m", "aicg", "--root", str(root), *args],
                            capture_output=True, text=True, check=False)
    if result.returncode == 2:
        raise RuntimeError(result.stderr)
    return result.returncode, json.loads(result.stdout)


def scenario(base, name):
    root = base / name
    init_repo(root)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    data = yaml.safe_load((root / "policy.yaml").read_text())
    data["completion"]["independent_verification_required"] = True
    data["verifier"] = {"issuer": FIXTURE_ISSUER, "key": FIXTURE_PUBLIC_KEY,
                        "provider": FIXTURE_PROVIDER, "model": FIXTURE_MODEL}
    counts = json.dumps({"critical": 0, "high": 1 if name == "security-threshold-fail" else 0})
    data["commands"].update({
        "build": [sys.executable, "-c", f"raise SystemExit({1 if name == 'build-fail' else 0})"],
        "test": [sys.executable, "-c", f"raise SystemExit({1 if name == 'test-fail' else 0})"],
        "security": [sys.executable, "-c", f"print({counts!r})"],
    })
    (root / "policy.yaml").write_text(yaml.safe_dump(data))
    cli(root, "gate", "run")
    if name != "missing-verifier":
        request = VerifierInput.model_validate(cli(root, "verifier", "request")[1])
        report = VerifierReport(
            status="REPAIR_REQUIRED" if name == "verifier-reject" else "PASS",
            failed_criteria=[], architecture_concerns=[], security_concerns=[],
            missing_evidence=[], repair_instructions=[])
        external = sign_verifier_report(request, report, FIXTURE_KEY, issuer=FIXTURE_ISSUER,
                                        provider=FIXTURE_PROVIDER, model=FIXTURE_MODEL)
        file = base / f"{name}-verifier.json"
        file.write_text(external.model_dump_json())
        cli(root, "verifier", "import", str(file))
    code, result = cli(root, "gate", "final")
    expected = "PASS" if name == "all-pass" else "REJECT"
    if result["status"] != expected or code != (0 if expected == "PASS" else 1):
        raise RuntimeError(f"{name}: unexpected {result}")
    return {"scenario": name, "expected": expected, "actual": result["status"], "exit_code": code}


def main():
    with tempfile.TemporaryDirectory(prefix="aicg-examples-") as directory:
        results = [scenario(Path(directory), name) for name in (
            "all-pass", "build-fail", "test-fail", "missing-verifier", "verifier-reject", "security-threshold-fail")]
    report = {"fixture_only": True, "scenarios": results}
    output = Path(".ai/runs/examples-summary.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
