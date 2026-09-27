"""CLI entry point. Results are JSON; process status is stable."""

import argparse
import json
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from aicg import __version__
from aicg.adapters import compile_policy, doctor, generate_ci, init_repo
from aicg.core import GovernanceError, workflow
from aicg.evidence import CommandEvidence, ExternalEvidence
from aicg.gates import exit_status, final_gate, redact, run_gates
from aicg.policy import Policy, action_check, load_policy
from aicg.verifier import VerifierInput, import_evidence, verifier_request


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aicg", description="Deterministic AI coding governance")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--root", type=Path, default=Path.cwd(), help="Git repository root")
    commands = p.add_subparsers(dest="command", required=True)
    for name in ("init", "compile", "doctor"):
        commands.add_parser(name)
    policy = commands.add_parser("policy").add_subparsers(dest="operation", required=True)
    policy.add_parser("validate")
    policy.add_parser("schema")
    gate = commands.add_parser("gate").add_subparsers(dest="operation", required=True)
    gate.add_parser("run").add_argument("--dry-run", action="store_true")
    gate.add_parser("final")
    state = commands.add_parser("workflow").add_subparsers(dest="operation", required=True)
    state.add_parser("show")
    state.add_parser("transition").add_argument("target")
    ci = commands.add_parser("ci").add_subparsers(dest="operation", required=True)
    ci.add_parser("generate").add_argument("provider", choices=["github"])
    approval = commands.add_parser("approval").add_subparsers(dest="operation", required=True)
    approval.add_parser("check").add_argument("action")
    verifier = commands.add_parser("verifier").add_subparsers(dest="operation", required=True)
    verifier.add_parser("request")
    verifier.add_parser("import").add_argument("file", type=Path)
    commands.add_parser("schema").add_argument("kind", choices=["policy", "command", "external", "verifier-input"])
    return p


def dispatch(args) -> tuple[dict, int]:
    root = args.root.resolve()
    if args.command == "init":
        return init_repo(root), 0
    if args.command == "schema":
        models: dict[str, type[BaseModel]] = {"policy": Policy, "command": CommandEvidence, "external": ExternalEvidence,
                 "verifier-input": VerifierInput}
        return models[args.kind].model_json_schema(), 0
    if args.command == "policy" and args.operation == "schema":
        return Policy.model_json_schema(), 0
    if args.command == "workflow":
        return workflow(root, getattr(args, "target", None)), 0
    if args.command == "ci":
        return generate_ci(root), 0
    if args.command == "doctor":
        result = doctor(root)
        return result, exit_status(result)
    policy = load_policy(root)
    if args.command == "policy":
        return {"status": "PASS", "schema_version": policy.version}, 0
    if args.command == "compile":
        return compile_policy(root, policy), 0
    if args.command == "approval":
        result = action_check(policy, args.action)
        return result, exit_status(result)
    if args.command == "verifier":
        return (verifier_request(root, policy) if args.operation == "request"
                else import_evidence(root, policy, args.file)), 0
    result = (run_gates(root, policy, args.dry_run) if args.operation == "run" else final_gate(root, policy))
    return result, 0 if result.get("dry_run") else exit_status(result)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result, status = dispatch(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return status
    except ValidationError as exc:
        # ValidationError's default representation echoes inputs, potentially secrets.
        errors = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        print(json.dumps({"status": "ERROR", "validation_errors": errors}), file=sys.stderr)
        return 2
    except (OSError, GovernanceError, ValueError, yaml.YAMLError) as exc:
        print(json.dumps({"status": "ERROR", "message": redact(str(exc))}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('{"status":"ERROR","message":"interrupted; current run remains incomplete"}', file=sys.stderr)
        return 130
