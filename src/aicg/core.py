"""Filesystem boundaries and workflow transitions."""

import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath


class GovernanceError(ValueError):
    """Invalid configuration or unsafe operation."""


def relative_path(value: str) -> str:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or "\\" in value or ":" in value:
        raise GovernanceError("path must be relative and cannot contain traversal")
    if str(p) != value or value == "." or "\x00" in value:
        raise GovernanceError("path must be normalized")
    return value


def safe_path(root: Path, value: str) -> Path:
    relative_path(value)
    root = root.resolve()
    current = root
    for part in PurePosixPath(value).parts:
        current /= part
        if current.is_symlink():
            raise GovernanceError(f"symlink path rejected: {value}")
    if not current.resolve().is_relative_to(root):
        raise GovernanceError(f"path escapes repository: {value}")
    return current


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def write_bytes(root: Path, name: str, content: bytes) -> None:
    path = safe_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(root: Path, name: str, value: object) -> None:
    write_bytes(root, name, json_bytes(value))


def read_json(root: Path, name: str) -> dict:
    path = safe_path(root, name)
    if path.stat().st_size > 4_000_000:
        raise GovernanceError("JSON document too large")
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise GovernanceError("expected JSON object")
    return result


def create_files(root: Path, files: dict[str, bytes]) -> list[str]:
    """Preflight all conflicts before writing any generated file."""
    for name, content in files.items():
        path = safe_path(root, name)
        if path.exists() and (not path.is_file() or path.read_bytes() != content):
            raise GovernanceError(f"conflicting file: {name}; review diff and move it explicitly")
    created = []
    for name, content in files.items():
        path = safe_path(root, name)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
            created.append(name)
    return created


TRANSITIONS = {
    "DISCOVER": {"SPECIFY", "BLOCKED"},
    "SPECIFY": {"ARCHITECT", "BLOCKED"},
    "ARCHITECT": {"IMPLEMENT", "BLOCKED"},
    "IMPLEMENT": {"BUILD", "BLOCKED"},
    "BUILD": {"TEST", "REPAIR", "BLOCKED"},
    "TEST": {"VERIFY", "REPAIR", "BLOCKED"},
    "VERIFY": {"SUBMIT", "REPAIR", "BLOCKED"},
    "SUBMIT": {"DISCOVER"},
    "REPAIR": {"IMPLEMENT", "BUILD", "BLOCKED"},
    "BLOCKED": {"DISCOVER", "REPAIR"},
}


def workflow(root: Path, target: str | None = None) -> dict:
    name = ".ai/workflow.json"
    state = read_json(root, name) if safe_path(root, name).exists() else {"state": "DISCOVER"}
    if state.get("state") not in TRANSITIONS:
        raise GovernanceError("invalid stored workflow state")
    if target is not None:
        if target not in TRANSITIONS[state["state"]]:
            raise GovernanceError(f"illegal transition: {state['state']} -> {target}")
        state = {"state": target}
        write_json(root, name, state)
    return state
