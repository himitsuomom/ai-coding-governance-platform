import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from aicg.adapters import DOCUMENTS, init_repo
from aicg.evidence import now
from aicg.gates import current_context
from aicg.policy import load_policy
from aicg.verifier import import_evidence


def configure(root, **changes):
    data = yaml.safe_load((root / "policy.yaml").read_text())
    for section, values in changes.items():
        if isinstance(values, dict):
            data[section].update(values)
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
    })
    return root


def external(root: Path, status="PASS", kind="verifier", **changes):
    binding, _ = current_context(root, load_policy(root))
    report = {"status": status, "failed_criteria": [], "architecture_concerns": [],
              "security_concerns": [], "missing_evidence": [], "repair_instructions": []}
    body = {**binding, "schema_version": 1, "kind": kind, "producer": "external",
            "reviewer": "TEST FIXTURE ONLY", "recorded_at": now(), "report": report}
    body.update(changes)
    file = root.parent / f"{kind}-fixture.json"
    file.write_text(json.dumps(body))
    import_evidence(root, load_policy(root), file)
    return file
