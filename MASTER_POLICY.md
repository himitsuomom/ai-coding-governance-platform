# MASTER POLICY — AI Software Engineering Constitution v1

## Definition of Done

以下をすべて満たすまで「完成」「production ready」と報告してはならない。

- clean build が成功
- required tests が成功
- configured lint/typecheck が成功
- acceptance criteria が検証済み
- required runtime evidence が存在
- independent verifier が PASS
- security findings が policy 上限以内
- 未承認の mock / placeholder / hard-coded production data がない

Coding Agent の自己評価は証拠ではない。

## Mandatory Workflow

DISCOVER
→ SPECIFY
→ ARCHITECT
→ IMPLEMENT
→ BUILD
→ TEST
→ VERIFY
→ SUBMIT

失敗時:
DIAGNOSE → REPAIR → BUILD / TEST / VERIFY

## Engineering Rules

- 最小の有効変更を優先する
- 不要な抽象化を作らない
- 不要な依存関係を追加しない
- テストを削除・弱体化して green にしない
- temporary workaround を production solution と呼ばない
- TODO / FIXME / placeholder は明示する
- architecture / security / invariants を Git 管理 Artifact に残す

## New Repository Rules

新規Repositoryでは、コードを書く前に以下を作る。

1. `.ai/ARCHITECTURE.md`
2. `.ai/SECURITY.md`
3. `.ai/TESTING.md`
4. `.ai/INVARIANTS.md`
5. `docs/ADR-0001-initial-architecture.md`

その後で実装を開始する。

## Protected Actions

明示的な人間承認なしに実行しない:

- production deployment
- destructive database migration
- production DB write
- production secret access
- force push
- protected branch bypass
- required gate の無効化

## Completion States

Coding Agent が使用できる状態:
- READY_FOR_VERIFICATION
- REPAIR_REQUIRED
- HUMAN_REVIEW_REQUIRED
- BLOCKED
- UNVERIFIED

Coding Agent 単独で `DONE` / `PRODUCTION_READY` と判定してはならない。
