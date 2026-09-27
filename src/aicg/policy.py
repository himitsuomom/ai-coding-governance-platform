"""Strict policy validation; no executable configuration loading."""

import shlex
from pathlib import Path, PurePosixPath
from typing import Literal, get_args, get_origin

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aicg.core import GovernanceError, relative_path, safe_path


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="before")
    @classmethod
    def exact_literals(cls, data):
        if isinstance(data, dict):
            for name, field in cls.model_fields.items():
                if name in data and get_origin(field.annotation) is Literal:
                    allowed = get_args(field.annotation)
                    if not any(type(data[name]) is type(value) and data[name] == value for value in allowed):
                        raise GovernanceError(f"invalid literal type/value: {name}")
        return data


class Completion(StrictModel):
    build_required: bool
    tests_required: bool
    typecheck_required: bool
    lint_required: bool
    runtime_validation_required: bool
    independent_verification_required: bool


class Security(StrictModel):
    max_critical_findings: int = Field(ge=0)
    max_high_findings: int = Field(ge=0)
    allow_production_secret_access: Literal[False]
    allow_production_db_write: Literal[False]
    allow_force_push: Literal[False]
    allow_gate_disable: Literal[False]
    required: bool = True


class Approval(StrictModel):
    production_deploy: bool
    destructive_migration: bool
    auth_boundary_change: bool
    disable_required_gate: bool


Command = str | list[str]


def argv(command: Command) -> list[str]:
    result = shlex.split(command) if isinstance(command, str) else command
    if any(not part or "\x00" in part for part in result):
        raise GovernanceError("invalid empty/NUL command argument")
    return result


class Commands(StrictModel):
    build: Command
    test: Command
    typecheck: Command
    lint: Command
    security: Command
    runtime: Command = ""

    @field_validator("*")
    @classmethod
    def validate_command(cls, value):
        argv(value)
        return value


class EvidencePaths(StrictModel):
    verifier_result: str
    runtime_result: str
    security_result: str

    @field_validator("*")
    @classmethod
    def validate_path(cls, value):
        relative_path(value)
        if not value.startswith(".ai/evidence/") or not value.endswith(".json"):
            raise GovernanceError("evidence path must be .ai/evidence/*.json")
        return value

    @model_validator(mode="after")
    def distinct(self):
        values = list(self.model_dump().values())
        reserved = {f".ai/evidence/{name}.json" for name in ("build", "test", "lint", "typecheck", "current")}
        if len(set(values)) != len(values) or reserved.intersection(values):
            raise GovernanceError("evidence paths collide")
        paths = [PurePosixPath(value) for value in [*values, *reserved]]
        if any(left in right.parents for left in paths for right in paths if left != right):
            raise GovernanceError("evidence paths have ancestor collisions")
        return self


class Policy(StrictModel):
    version: Literal[1]
    completion: Completion
    security: Security
    human_approval: Approval
    commands: Commands
    evidence: EvidencePaths
    adapters: list[Literal["codex", "openhands", "generic"]] = ["codex", "openhands", "generic"]
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    max_output_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)

    @model_validator(mode="after")
    def configured(self):
        if not self.adapters or len(set(self.adapters)) != len(self.adapters):
            raise GovernanceError("adapters must be nonempty and unique")
        for gate, required in self.required_commands().items():
            if required and not argv(getattr(self.commands, gate)):
                raise GovernanceError(f"required command is empty: {gate}")
        return self

    def required_commands(self) -> dict[str, bool]:
        c = self.completion
        return {"build": c.build_required, "test": c.tests_required,
                "lint": c.lint_required, "typecheck": c.typecheck_required,
                "security": self.security.required}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise GovernanceError("YAML mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_policy(root: Path) -> Policy:
    path = safe_path(root, "policy.yaml")
    if path.stat().st_size > 100_000:
        raise GovernanceError("policy too large")
    data = yaml.load(path.read_text(), Loader=UniqueLoader)  # nosec B506: SafeLoader subclass
    result = Policy.model_validate(data)
    for name in result.evidence.model_dump().values():
        safe_path(root, name)
    return result


def action_check(policy: Policy, action: str) -> dict:
    approvals = policy.human_approval.model_dump()
    required = approvals.get(action, True)
    if action in {"disable_required_gate", "production_secret_access", "production_db_write", "force_push"}:
        required = True
    return {"action": action, "status": "HUMAN_REVIEW_REQUIRED" if required else "PASS",
            "executed": False}
