# Project Specification — AI Coding Governance Platform

## 1. Product Goal

既存の AI Coding Agent（Codex、OpenHands、Claude系ツール、将来のOpen-weight Agent等）を、
**共通Policy・独立Verifier・CI Hard Gateの下で統制する、モデル非依存のAIソフトウェア開発ガバナンス基盤**
を構築する。

このプロジェクトは独自LLM、独自Sandbox、巨大Multi-Agent Orchestratorを再実装しない。

中核価値は以下の4点に限定する。

1. 1つの `MASTER_POLICY` から Agentごとの指示書を生成する。
2. 自然言語ルールと機械的Hard Gateを分離する。
3. Coding Agentの自己評価とIndependent Verificationを分離する。
4. 「見た目だけ動く」「テストを通しただけ」のコードを完成扱いしない。

---

## 2. Product Name

Working name:

`ai-coding-governance-platform`

CLI command candidate:

`aicg`

命名は実装前にADRで確定する。

---

## 3. Primary Users

### 3.1 Individual Developer

Codex / OpenHands 等を使って開発する個人開発者。

必要なもの:

- RepositoryへPolicyを簡単に導入
- Agentごとの指示ファイルを自動生成
- Build/Test/Verifierを一括実行
- 「本当に検証済みか」を機械的に判定

### 3.2 Engineering Team

AI Coding Agentをチームで利用する開発組織。

必要なもの:

- 共通Policy
- CI enforcement
- branch protectionとの接続
- evidence保存
- audit可能な結果

### 3.3 Platform / Security Engineer

複数Repositoryに共通ルールを展開したい担当者。

必要なもの:

- Policy as Code
- Adapter
- Security Gate
- Human Approval boundary
- machine-readable evidence

---

## 4. Core Design Principles

### 4.1 Model Independence

Policy / Gate / Evidence形式は特定モデルに依存しない。

以下を交換可能にする。

- Codex
- OpenHands
- Claude系Coding Agent
- Open-weight Coding Agent

### 4.2 Fail Closed

Evidenceが不足する場合はPASSにしない。

`unknown = success` にしてはならない。

### 4.3 Agent Self-Assessment Is Not Evidence

Coding Agent自身の

- 「完成しました」
- 「問題ありません」
- 「production readyです」

という文章は完成判定に使用しない。

### 4.4 Soft Rule / Hard Rule Separation

自然言語でしか判断できない規則と、
CIで強制可能な規則を分離する。

### 4.5 Repository as Long-Term Memory

v1では専用Vector DB / Graph DB / Memory Serverを導入しない。

長期的なProject MemoryはGit管理されたArtifactを使う。

### 4.6 Smallest Useful System

v1では以下を実装しない。

- 独自LLM
- 独自Sandbox
- 独自Vector Database
- 独自Graph Memory
- 大規模Multi-Agent Orchestrator
- Model fine-tuning
- Production deployment engine

---

## 5. Functional Requirements

# FR-001 — Repository Initialization

CLIから既存または新規RepositoryへGovernance layerを導入できる。

Example:

```bash
aicg init
```

生成対象:

```text
MASTER_POLICY.md
policy.yaml
AGENTS.md
.ai/
verifier/
.github/workflows/
```

既存ファイルを勝手に上書きしてはならない。

競合時はdiffまたは明示的なconfirmationを要求する。

---

# FR-002 — Master Policy

Repositoryに1つのCanonical Policyを持つ。

```text
MASTER_POLICY.md
policy.yaml
```

役割:

- `MASTER_POLICY.md`
  - Human-readable
  - Agent-readable
  - Engineering principles

- `policy.yaml`
  - machine-readable
  - build/test/security条件
  - human approval境界
  - evidence path
  - completion条件

---

# FR-003 — Policy Compilation

Canonical PolicyからAgent向けInstructionを生成できる。

Initial adapters:

1. Codex
2. OpenHands
3. Generic `AGENTS.md`

Example:

```bash
aicg compile
```

Output examples:

```text
generated/codex/AGENTS.md
generated/openhands/INSTRUCTIONS.md
generated/generic/AGENTS.md
```

生成物には、

> GENERATED FILE — DO NOT EDIT DIRECTLY

を明記する。

手編集はCanonical Policyへ反映させる。

---

# FR-004 — Policy Validation

`policy.yaml` をSchema validationする。

Example:

```bash
aicg policy validate
```

検出対象:

- 必須キー欠落
- 型不整合
- invalid completion rule
- evidence path invalid
- command requirementとcommand未設定の矛盾
- security threshold invalid
- unsupported adapter

Validation error時はnon-zero exit code。

---

# FR-005 — Fixed Workflow State

Coding workflowの状態を機械的に表現する。

Minimum states:

```text
DISCOVER
SPECIFY
ARCHITECT
IMPLEMENT
BUILD
TEST
VERIFY
SUBMIT
REPAIR
BLOCKED
```

Illegal transitionは拒否する。

状態はmachine-readableで保存可能にする。

---

# FR-006 — Build/Test Gate Runner

Policyに定義されたcommandを実行できる。

Example:

```bash
aicg gate run
```

対象:

- build
- test
- typecheck
- lint
- security

各commandについて記録する。

- start time
- end time
- exit code
- stdout/stderr location
- PASS/FAIL

Agentの自然言語報告だけでPASSにしない。

---

# FR-007 — Evidence Store

Evidenceを `.ai/evidence/` に機械可読形式で保存する。

Minimum:

```text
.ai/evidence/
├── build.json
├── test.json
├── typecheck.json
├── lint.json
├── security.json
├── runtime.json
└── verifier.json
```

Common fields:

```json
{
  "schema_version": 1,
  "status": "PASS",
  "command": "...",
  "exit_code": 0,
  "started_at": "...",
  "finished_at": "...",
  "artifact_paths": []
}
```

Evidenceを捏造するAPIを作ってはならない。

Runner自身が生成したEvidenceと、
外部Verifierが生成したEvidenceを区別する。

---

# FR-008 — Independent Verifier Contract

Coding Agentとは独立したVerifierのInput/Output schemaを定義する。

Input:

- original requirement
- acceptance criteria
- git diff
- build result
- test result
- runtime evidence when required
- security evidence when required
- architecture/invariant documents

Output:

```json
{
  "status": "PASS",
  "failed_criteria": [],
  "architecture_concerns": [],
  "security_concerns": [],
  "missing_evidence": [],
  "repair_instructions": []
}
```

Allowed statuses:

- `PASS`
- `REPAIR_REQUIRED`
- `HUMAN_REVIEW_REQUIRED`
- `INSUFFICIENT_EVIDENCE`

Verifier Provider自体はpluggableにする。v1には汎用Provider interfaceと、継続無料枠で利用できるCloudflare Workers AI adapterを含める。特定商用APIの有料credentialは必須にしない。

Verifier reportをCIで独立Evidenceとして扱う場合、Ed25519署名付きattestationを必須にする。署名対象はissuer、key ID、run/policy/source binding、VerifierInput全体のSHA-256、model/provider識別子、reportを含むcanonical JSONとする。未署名のVerifier evidenceや不明な鍵はPASSにできない。Runtime evidenceの既存手動import形式は本要件の対象外。

信頼済みCIはPR変更可能なコードを実行せず、差分と必要なsourceだけをread-only dataとしてVerifierへ渡す。API tokenと署名秘密鍵は信頼済みVerifier stepだけに渡し、PR実行step・候補コード・artifactには渡さない。信頼済み公開鍵はPRで変更できないCI設定にもpinする。Provider障害、署名不正、日次無料枠超過はfail closedとする。

受け入れ条件:

- reportが現在のrun、policy、source、完全なVerifierInputに結び付く。
- 不明なissuer/key、署名欠落・改ざん・別runへの再利用、旧unsigned Verifier evidenceを拒否する。
- PASS reportに未解決concernがあれば拒否する。
- 外部CIは対象PRのプログラムやscriptを実行せずにreviewを行い、その信頼状態を必須statusとして報告する。
- 無料枠切れとProvider/API障害ではVerifier PASSを発行しない。有料planへの自動切替をしない。

---

# FR-009 — Final Production Gate

Example:

```bash
aicg gate final
```

以下を集約して最終判定する。

```text
Build
AND Tests
AND required Type/Lint
AND Security thresholds
AND Runtime evidence if required
AND Independent Verifier
```

Output:

```text
PASS
REJECT
HUMAN_REVIEW_REQUIRED
```

CLI exit codeも意味を持たせる。

推奨:

- 0 = PASS
- 1 = REJECT
- 2 = configuration/error
- 3 = HUMAN_REVIEW_REQUIRED

最終判定ロジックはLLMに任せない。

---

# FR-010 — Human Approval Boundaries

次のようなActionはPolicyでHuman Approvalを要求できる。

- production deploy
- destructive migration
- auth boundary change
- disabling required gate
- production secret access
- production DB write

v1では実際にProductionへActionを実行する必要はない。

必要なのは、

> このActionは自動実行不可

をmachine-readableに判断できること。

---

# FR-011 — Project Memory Artifacts

以下を標準Artifactとして扱う。

```text
.ai/
├── ARCHITECTURE.md
├── SECURITY.md
├── TESTING.md
├── INVARIANTS.md
├── specs/
├── adr/
└── known-issues/
```

CLI:

```bash
aicg doctor
```

で不足Artifactを検出できる。

---

# FR-012 — Doctor Command

RepositoryのAI Coding readinessを検査する。

Example:

```bash
aicg doctor
```

確認:

- Git repositoryか
- Policy存在
- Policy schema valid
- required `.ai` files存在
- configured command存在
- evidence directory書込可能
- generated Agent instructionsがstaleでない
- CI config存在

Exit code:

- 0 = healthy
- non-zero = issues detected

---

# FR-013 — Dry Run

Gate commandを実行せず、
何が実行される予定か表示できる。

```bash
aicg gate run --dry-run
```

CI導入前の安全確認用。

---

# FR-014 — Audit Output

1回のGate実行についてsummaryを生成する。

Example:

```text
.ai/runs/<run-id>/
├── manifest.json
├── build.log
├── test.log
├── security.log
└── summary.json
```

run-idは衝突しない形式を使用する。

---

# FR-015 — CI Integration

最低限GitHub Actions用workflow templateを生成できる。

```bash
aicg ci generate github
```

CIではRepository checkout後、

```bash
aicg policy validate
aicg gate run
aicg gate final
```

を実行可能にする。

GitHub以外のCIはv1必須ではない。

---

# FR-016 — Safe Command Execution

Gate runnerは、Policyで明示されたcommandだけを実行する。

以下を避ける。

- arbitrary remote command ingestion
- hidden shell injection
- implicit production credential access

command execution boundaryをSecurity設計で明記する。

---

## 6. Non-Functional Requirements

### NFR-001 — Reliability

Gate判定は同じ入力Evidenceに対しdeterministicであること。

### NFR-002 — Security

- secretをlogへ出さない
- env valueをEvidenceへ無差別保存しない
- path traversalを防ぐ
- evidence pathをRepository外へescapeさせない
- command injection riskをDocumentする
- defaultでproduction credentialを要求しない

### NFR-003 — Maintainability

Core domainとProvider Adapterを分離する。

推奨概念:

```text
core/
policy/
evidence/
gates/
adapters/
cli/
```

ただし不要なClean Architecture化を避ける。

### NFR-004 — Portability

macOS / Linuxをv1対象とする。

Windowsはbest effortまたは後続。

### NFR-005 — Observability

CLI failureには、

- failed gate
- command
- exit code
- evidence path

を明示する。

### NFR-006 — Performance

このプロジェクト自身がLLM推論を行わない場合、
通常のpolicy validation / final gate判定は数秒以内を目標とする。

Build/Test commandの時間は除外。

### NFR-007 — Dependency Discipline

小規模CLIとして開始し、依存追加を最小限にする。

新規dependencyはADRまたはREADMEで理由を説明できること。

---

## 7. Recommended Initial Stack

実装Agentは最終決定をADRへ記録する。

第一候補:

```text
Language: Python 3.12+
Packaging: pyproject.toml
CLI: Typer or argparse
Config: YAML
Schema: Pydantic / JSON Schema / equivalent
Tests: pytest
CI: GitHub Actions
```

ただし、
より小さく安全な構成があれば変更可能。

変更理由は `docs/ADR-0001-initial-architecture.md` に記録する。

---

## 8. Required Repository Structure

Minimum target:

```text
ai-coding-governance-platform/
├── README.md
├── LICENSE
├── pyproject.toml
├── MASTER_POLICY.md
├── policy.yaml
├── AGENTS.md
│
├── src/
│   └── ...
│
├── tests/
│   └── ...
│
├── adapters/
│   ├── codex/
│   ├── openhands/
│   └── generic/
│
├── verifier/
│   └── ...
│
├── .ai/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── TESTING.md
│   ├── INVARIANTS.md
│   ├── evidence/
│   ├── specs/
│   ├── adr/
│   └── known-issues/
│
├── docs/
│   └── ADR-0001-initial-architecture.md
│
└── .github/
    └── workflows/
```

実装言語に合わせて調整可。

---

## 9. Acceptance Criteria

### AC-001 Initialization

空ディレクトリで初期化コマンドを実行すると、
必要なPolicy/AI governance filesが生成される。

既存ファイルは無断上書きされない。

### AC-002 Policy Validation

valid policyは成功し、
invalid policyはnon-zero exit codeで失敗する。

### AC-003 Instruction Compilation

1つのMaster Policyから、
少なくともCodex/OpenHands/Generic用instructionを生成できる。

### AC-004 Build Failure Blocks Completion

dummy repositoryのbuild commandがfailした場合、
Final GateはPASSしない。

### AC-005 Test Failure Blocks Completion

test commandがfailした場合、
Final GateはPASSしない。

### AC-006 Missing Verifier Blocks Completion

`independent_verification_required=true`
かつVerifier evidenceなしの場合、
Final GateはPASSしない。

### AC-007 Verifier Reject Blocks Completion

Verifier statusが`REPAIR_REQUIRED`の場合、
Final GateはREJECTする。

### AC-008 Security Threshold

critical/high findingsがpolicy thresholdを超える場合、
Final GateはREJECTする。

### AC-009 Runtime Requirement

`runtime_validation_required=true`
の場合、runtime evidenceなしではPASSしない。

### AC-010 Human Approval

Human Approval対象Actionは自動PASSせず、
`HUMAN_REVIEW_REQUIRED`として扱える。

### AC-011 No Self-Assessment Completion

Coding Agentのテキスト出力だけでは
Final GateのPASS状態を生成できない。

### AC-012 Evidence Auditability

各Gate実行後に、
何が実行され、何が成功/失敗したか機械可読に追跡できる。

### AC-013 Doctor

Policyや必須Artifactが不足するRepositoryで
`aicg doctor` が問題を報告する。

### AC-014 Dry Run

`--dry-run`では外部build/test commandを実行しない。

### AC-015 CI

GitHub Actions上でpolicy validationとgateを実行できる。

---

## 10. Required Tests

Minimum:

### Unit

- policy parser
- schema validation
- workflow transitions
- final gate logic
- path safety
- status mapping

### Integration

- temporary Git repository init
- policy compilation
- successful fake build/test
- failing build
- failing test
- missing verifier
- verifier reject
- security threshold reject
- runtime evidence required/missing

### Security-focused tests

- evidence path traversal
- malformed YAML
- shell command failure
- log redaction behavior where implemented

### CLI tests

- exit codes
- help
- invalid config
- dry-run

---

## 11. Production Readiness Rules

v1が「完成」と言えるには最低限:

- all required tests pass
- package installation works from clean environment
- CLI help works
- GitHub Actions passes
- no critical/high security issue detected by configured scanner
- README has installation + quickstart
- example project demonstrates FAIL and PASS behavior
- Independent Verifier contract documented
- limitations documented

---

## 12. Example User Flow

```bash
git init my-project
cd my-project

aicg init

# edit policy
vim policy.yaml

aicg policy validate
aicg compile
aicg doctor

# coding agent works here

aicg gate run

# verifier evidence is produced/imported here

aicg gate final
```

Expected final output example:

```text
BUILD       PASS
TEST        PASS
TYPECHECK   PASS
SECURITY    PASS
RUNTIME     NOT_REQUIRED
VERIFIER    PASS

FINAL       PASS
```

Failure example:

```text
BUILD       PASS
TEST        PASS
VERIFIER    MISSING

FINAL       REJECT
reason: independent verification is required
```

---

## 13. Explicit Non-Goals for v1

Do NOT implement unless clearly required by an acceptance criterion:

- custom LLM
- model training
- model hosting
- custom sandbox/container runtime
- distributed orchestration
- multi-agent chat framework
- Vector DB
- Graph DB
- browser automation platform
- production deploy engine
- secret manager
- full web dashboard
- billing
- team RBAC
- SaaS control plane

---

## 14. Future Roadmap

### v2

- CAID-style parallel workers
- git worktree isolation
- task DAG
- multiple verifier providers
- more CI providers

### v3

- repository-specific trajectory collection
- SERA-style specialization
- benchmark harness

### v4

- dynamic agent topology
- advanced long-term memory
- OpenSage-like agent generation

これらはv1 acceptance criteriaを満たした後のみ検討する。

---

## 15. Definition of Success

このプロジェクトの成功は、

> 「強いCoding Agentを作れたか」

ではない。

成功条件は、

> **異なるCoding Agentを同一Policyの下で動かし、Agent自身では回避できないEvidence-based Gateによって、未検証コードを完成扱いしない仕組みを提供できたか**

である。
