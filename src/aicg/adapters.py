"""Repository bootstrap, instruction compilation and CI diagnostics."""

import os
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from aicg.core import GovernanceError, create_files, digest, json_bytes, safe_path
from aicg.evidence import git
from aicg.policy import Policy, argv, load_policy

DOCUMENTS = ("ARCHITECTURE", "SECURITY", "TESTING", "INVARIANTS")
OUTPUTS = {"codex": "generated/codex/AGENTS.md", "openhands": "generated/openhands/INSTRUCTIONS.md",
           "generic": "generated/generic/AGENTS.md"}
CI_PATH = ".github/workflows/aicg.yml"


def ci_content(require_verifier: bool = True) -> bytes:
    content = b'''# GENERATED FILE - DO NOT EDIT DIRECTLY
name: AI governance gate
on: [push, pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  gate:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
      - name: Install trusted governance tool
        env:
          AICG_INSTALL_SPEC: ${{ vars.AICG_INSTALL_SPEC }}
        run: |
          test -n "$AICG_INSTALL_SPEC"
          python -m pip install "$AICG_INSTALL_SPEC"
      - run: aicg policy validate
      - run: aicg gate run
      # VERIFIER_STEP
      - run: aicg gate final
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        if: always()
        with:
          name: governance-evidence
          path: |
            .ai/runs/
            .ai/evidence/
          include-hidden-files: true
'''
    verifier_step = b'''      - name: Export independent verification input
        run: aicg verifier request > .ai/runs/verifier-input.json
      # Import a trusted external report before the final gate.
'''
    return content.replace(b"      # VERIFIER_STEP\n", verifier_step if require_verifier else b"")


def init_repo(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    base = files("aicg").joinpath("templates")
    generated = {}

    def walk(node, prefix=""):
        for child in node.iterdir():
            name = prefix + child.name
            if child.is_dir():
                walk(child, name + "/")
            else:
                generated[name] = child.read_bytes()

    walk(base)
    generated[CI_PATH] = ci_content()
    for directory in (".ai/specs", ".ai/adr", ".ai/known-issues", ".ai/evidence"):
        generated[f"{directory}/.gitkeep"] = b""
    created = create_files(root, generated)
    return {"created": created, "next": "Configure policy.yaml commands and project-specific .ai documents."}


def compiled_files(root: Path, policy: Policy) -> dict[str, bytes]:
    master = safe_path(root, "MASTER_POLICY.md").read_text()
    fingerprint = digest(master.encode() + json_bytes(policy.model_dump()))
    result = {}
    for adapter in policy.adapters:
        extra = ("Read this file as the repository instruction entry point."
                 if adapter in {"codex", "generic"} else "Use these instructions in the OpenHands agent context.")
        verifier_step = (", independent verification"
                         if policy.completion.independent_verification_required else "")
        text = (f"# GENERATED FILE — DO NOT EDIT DIRECTLY\n\nAdapter: {adapter}\n"
                f"Source fingerprint: {fingerprint}\n\n{extra}\n\n{master}\n\n"
                "## Machine-enforced requirements\n\n"
                f"Run `aicg policy validate`, `aicg gate run`{verifier_step}, then `aicg gate final`.\n"
                "A model's self-assessment is never completion evidence.\n\n```json\n"
                + json_bytes(policy.model_dump()).decode() + "```\n")
        result[OUTPUTS[adapter]] = text.encode()
    return result


def compile_policy(root: Path, policy: Policy) -> dict:
    return {"created": create_files(root, compiled_files(root, policy))}


def generate_ci(root: Path) -> dict:
    policy = load_policy(root)
    content = ci_content(policy.completion.independent_verification_required)
    return {"created": create_files(root, {CI_PATH: content})}


def doctor(root: Path) -> dict:
    issues = []
    try:
        git(root, "rev-parse", "--show-toplevel")
    except (OSError, ValueError):
        issues.append("Git repository missing")
    policy = None
    try:
        policy = load_policy(root)
    except (OSError, ValueError) as exc:
        issues.append(f"policy invalid: {exc}")
    for name in ("MASTER_POLICY.md", "PROJECT_SPEC.md", *(f".ai/{doc}.md" for doc in DOCUMENTS)):
        try:
            content = safe_path(root, name).read_text()
            if not content.strip() or "Initial placeholder." in content or "TODO:" in content:
                issues.append(f"unfinished artifact: {name}")
        except (OSError, ValueError):
            issues.append(f"missing/unsafe artifact: {name}")
    for name in (".ai/specs", ".ai/adr", ".ai/known-issues"):
        if not safe_path(root, name).is_dir():
            issues.append(f"missing directory: {name}")
    if policy:
        for gate, command in policy.commands.model_dump().items():
            parts = argv(command)
            if not parts:
                continue
            executable = parts[0]
            present = (os.access(root / executable, os.X_OK) if "/" in executable
                       else shutil.which(executable) is not None)
            if not present:
                issues.append(f"command not found: {gate}: {executable}")
        try:
            for name, expected in compiled_files(root, policy).items():
                if not safe_path(root, name).exists() or safe_path(root, name).read_bytes() != expected:
                    issues.append(f"generated instructions missing/stale: {name}")
        except (OSError, ValueError) as exc:
            issues.append(f"instruction compilation unavailable: {exc}")
    try:
        directory = safe_path(root, ".ai/evidence")
        if not directory.is_dir():
            raise GovernanceError("evidence directory missing")
        with tempfile.TemporaryFile(dir=directory) as stream:
            stream.write(b"probe")
    except (OSError, ValueError) as exc:
        issues.append(f"evidence not writable: {exc}")
    if not safe_path(root, CI_PATH).is_file():
        issues.append(f"CI configuration missing: {CI_PATH}")
    return {"status": "PASS" if not issues else "REJECT", "issues": issues}
