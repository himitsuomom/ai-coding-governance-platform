# Architecture
Python 3.12+ local CLI `aicg`. argparse supplies parsing; Pydantic supplies strict schemas and JSON Schema exports; PyYAML supplies safe configuration loading. No service, model runtime or UI.

Layers: policy.py validates configuration; core.py owns workflow and safe filesystem operations; evidence.py owns source binding and schemas; gates.py executes configured argv and evaluates deterministic gates; adapters.py initializes repositories, compiles agent instructions and generates CI; verifier.py defines a provider protocol and manual import; cli.py presents commands and exit codes.

Each run uses a UUID, a manifest, redacted command logs and JSON evidence. Current-run metadata points to the latest completed or interrupted attempt. Evidence binds to policy and source SHA-256 fingerprints. Final evaluation rejects stale or incomplete runs. Runner evidence cannot be imported through the public CLI. Verifier/runtime imports require matching context and preserve external provenance.

Commands run locally without implicit shell interpretation. Policy is executable, trusted configuration. The tool is not a sandbox or an authentication boundary. CI protection must separate writers, reviewers and gate administration.
