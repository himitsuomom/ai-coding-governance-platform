# Implementation Order

Codex should build v1 in this order:

1. Repository/package skeleton
2. Policy schema
3. Policy validator
4. Workflow state model
5. Evidence model
6. Gate evaluator
7. CLI
8. Instruction compiler
9. Codex/OpenHands/Generic adapters
10. Doctor
11. CI generation/integration
12. Independent verifier contract
13. Example fixture repositories
14. Unit + integration tests
15. README and quickstart

Do not add Multi-Agent, Vector DB, long-term semantic memory, or model training before v1 acceptance criteria pass.
