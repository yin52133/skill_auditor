# skill-auditor Specification

## Problem and Goal

Codex 和 Claude Code 的 skill 集合会长期积累重复、过期、误触发和结构不合规的问题。当前缺少一个统一工具，能跨两套生态做客观审计、归类、维护记录和自动审计触发。这个设计定义 `skill-auditor`：一个共享 Python 内核、双生态薄包装、静态硬校验与启发式分析分层、并带维护账本与 active-set 推荐的技能审计系统。`docs/spec/spec.md` 是当前完整设计；`docs/spec/checklist.json` 和 `docs/spec/update_history` 负责后续实现进度与设计变更记录。

## Scope and Non-Goals

In scope:

- 扫描 Codex 或 Claude Code 当前宿主生态下的 skill 根目录，并允许显式跨生态覆盖
- 审计 `SKILL.md`、生态专属伴随文件、资源目录和可选 eval 痕迹
- 区分 common / codex / claude 规则，不混成单一假规则集
- 产出确定性 findings、启发式 findings、聚类关系、active-set 推荐
- 维护 per-skill ledger 和全局 index
- 提供 `watch` 与 git hook 两种自动审计触发方式
- 维护本仓库的 `docs/spec/spec.md`、`docs/spec/checklist.json`、`docs/spec/update_history` 三类控制文件边界

Out of scope:

- 默认直接重写 `SKILL.md` 正文
- 默认联网轮询远程来源并自动同步 skill
- 充当 Codex 或 Claude 的插件安装器
- 在没有 runtime harness 时声称“已证明真实触发行为正确”
- 把 upstream `skill-creator` 流程整体搬进本项目

## System Boundaries

```text
User / Codex wrapper / Claude wrapper / Git hook / Watcher
  └── calls ──► skill-auditor CLI
                  ├── reads ──► host-resolved installed skill roots
                  │               (~/.codex/... or ~/.claude/...)
                  ├── reads ──► explicit target paths
                  ├── runs  ──► discovery + parsers + rules + analysis
                  ├── writes ──► runtime state root
                  │               (~/.local/state/skill-auditor/ by default)
                  └── prints ──► text/json/markdown report
```

Leaves unchanged:

- upstream `skill-creator` references
- Codex / Claude 自身的技能加载机制
- 技能安装来源和插件市场

## Ownership or Source of Truth

| Layer | Owns | Rebuildable |
|-------|------|-------------|
| Installed skill files | skill 的真实内容与结构 | No |
| `docs/spec/spec.md` | 本仓库当前完整设计 | No |
| `docs/spec/checklist.json` | 本仓库实现进度状态 | No |
| `docs/spec/update_history` | 本仓库设计变更记录 | No |
| `skill_ledger/<instance_id>.json` | 每个 skill instance 的维护记录与审计摘要 | Partial |
| `skill_index.json` | skill instance 索引与聚合视图 | Yes |
| `clusters.json` | 重叠/重复聚类结果 | Yes |
| `active_set.json` | 当前推荐启用集 | Yes |
| `audit_runs/<run_id>.json` | 单次审计输出快照 | Yes |

`skill_ledger` 是部分可重建的：自动生成字段可由重新审计恢复，人工填写的 `note` 和来源注释不能丢。

## Spec and Checklist Relationship

`docs/spec/spec.md` is the source of truth for design. `docs/spec/checklist.json` tracks implementation status only.

The relationship is strictly one-way:

- spec changes first; checklist reflects consequences
- a checklist item never drives a spec change; only the reverse is valid
- when a spec section changes, every affected checklist item must be updated in the same pass

When a spec change affects an implementation area that is not yet done, the affected checklist item must set `"spec_delta": true` to signal that there are spec changes the implementation has not yet caught up with. When an implementation lands that resolves the delta, `spec_delta` is cleared.

`spec_delta: true` does not block other checklist items. It is a flag for the implementer and reviewer to know that the spec and the code are temporarily out of sync in that area.

## Core Decisions

1. **What:** 规范只有一个 canonical spec 文件：`docs/spec/spec.md`。
   **Why:** 这个项目会持续迭代；完整设计必须始终能单独阅读，不依赖历史讨论。进度状态放 `docs/spec/checklist.json`，设计变更记录放单文件 `docs/spec/update_history`。
   **Reversal condition:** 仓库未来建立了更强、已被全仓接受的 canonical 设计文档位置。

2. **What:** `docs/spec/update_history` 是 spec 包里的单文件，不是目录；它必须保存带版本号的更新记录。
   **Why:** review checklist 要求每个用途只有一个 canonical source。这里真正重要的是 canonical 单文件、版本信息和更新记录；具体序列化格式不是关键约束。
   **Reversal condition:** revision log 规模增长到单文件不可审阅，并且仓库明确接受新的 canonical 位置。

3. **What:** 共享 Python 审计内核负责 discovery、rules、analysis、ledger、report、watch、hooks；Codex 和 Claude 仅保留薄包装。
   **Why:** 两套生态差异只体现在规则和呈现层，核心逻辑重复实现会漂移。
   **Reversal condition:** 两个生态的运行约束分叉到共享内核明显阻碍正确性。

4. **What:** 审计结果必须分为 `deterministic_findings` 与 `heuristic_findings`。
   **Why:** 静态规则可以客观判定；聚类、味道判断、触发风险不能伪装成硬事实。
   **Reversal condition:** 后续引入了可重复、可验证的 runtime harness，并把部分现有启发式升级为确定性检查。

5. **What:** 默认动作为 report + suggested patch，不直接改目标 skill。
   **Why:** 审计器的角色是客观评价和指出问题，不是无提示地重写技能。
   **Reversal condition:** 用户显式接受受限 auto-fix 范围，并为每类自动修复建立了稳定回归测试。

6. **What:** active-set 逻辑只推荐，不自动禁用；默认上限 `30`。
   **Why:** 需求是减少自动触发噪音，不是让工具暗自替用户删改生态。
   **Reversal condition:** 用户后续明确要求受控 active/archive 管理，并接受对应的持久化与回滚设计。

7. **What:** 默认只记录本地 provenance；远程源比较按需执行。
   **Why:** 每次审计都联网会降低稳定性，并把一个静态工具变成易脆弱的同步器。
   **Reversal condition:** 远程源一致性成为明确产品目标，并有稳定的认证与失败语义设计。

8. **What:** 全局 audit 的默认目标是当前宿主生态，不是 Codex 和 Claude 两边一起扫。
   **Why:** 用户在 Codex 中调用全局审计时默认关心 Codex skills，在 Claude Code 中同理。默认跨生态扫描会引入不相关噪音，也会模糊当前会话的上下文。
   **Reversal condition:** 产品未来明确把跨生态总览作为默认行为，并能证明这种默认不会降低信噪比。

9. **What:** 安全和隐私约束是硬审计门槛，既约束 `skill-auditor` 自己的 skill / hook / docs 包，也约束被审计的目标 skill。
   **Why:** skill、hook、script 本质上是可执行操作说明。硬编码密钥、私有数据、或可疑二进制执行模式不能作为“风格问题”处理，必须作为错误级问题处理。
   **Reversal condition:** 未来如果引入显式 allowlist 机制，仍然只能降低误报，不得取消对 secrets、privacy、和可疑执行模式的硬审计。

10. **What:** `skill-auditor` 必须能在 Codex 和 Claude Code 当前宿主中直接使用，不依赖单独配置的外部 API key、外部模型 endpoint、或独立审计服务。
    **Why:** 这个工具的目标是成为两套宿主环境中的直接可用能力，不是再挂一个第三方 API 客户端或外部后端。额外 API key 和服务接口会增加部署成本、泄露面和失效模式。
    **Reversal condition:** 只有当未来明确把外部服务模式定义成独立产品形态，并且与当前 host-native 模式分离时，才允许新增该能力。

## Runtime Flows

### Flow 1: Direct audit

```text
caller
  │
  ▼
resolve target roots
  │
  ├── no target found? ──► TARGET_NOT_FOUND
  │
  ▼
discover skill instances
  │
  ▼
parse SKILL.md and companions
  │
  ├── parse failure? ──► emit schema finding for that instance; continue
  │
  ▼
run deterministic rules
  │
  ▼
run optional host-native semantic analysis
  │
  ├── host-native analysis unavailable? ──► mark semantic_status=skipped
  │
  ▼
write audit run snapshot
  │
  ▼
update ledgers and global derived state
  │
  ▼
print report and return exit status
```

### Flow 2: Watch-triggered audit

```text
filesystem change
  │
  ▼
map changed file to owning skill instance
  │
  ├── no owning skill? ──► ignore event
  │
  ▼
debounce burst
  │
  ▼
fingerprint unchanged?
  │
  ├── yes ──► skip run
  │
  ▼
run instance audit
  │
  ▼
refresh ledger, index, clusters, active set
```

### Flow 3: Git hook gate

```text
git hook starts
  │
  ▼
collect staged changed files
  │
  ▼
resolve impacted skill instances
  │
  ▼
run deterministic checks only
  │
  ├── any error finding? ──► block commit / push
  │
  ▼
print warnings and allow commit / push
```

## Data and Interface Contracts

### Runtime entry: `skill-auditor audit`

```text
skill-auditor audit [path...]
  args.path              path[]   optional: skill dir, repo root, or explicit roots
  flag.--all             bool     optional: scan default installed roots for the current host ecosystem
  flag.--format          enum     optional: text/json/markdown
  flag.--ecosystem       enum     optional: host/codex/claude/both
  flag.--active-set-max  int      optional: override the recommended active-set cap (default: 30)

success → audit report emitted; exit 0 when no deterministic error blocks the requested mode
error INVALID_ARGUMENT      → exit non-zero; malformed flags or incompatible arguments
error TARGET_NOT_FOUND      → exit non-zero; no matching skill instance under requested target
error STATE_WRITE_FAILED    → exit non-zero; report computed but runtime state write failed
error ENGINE_BROKEN         → exit non-zero; internal invariant or unexpected fatal exception
error HOST_ECOSYSTEM_UNKNOWN → exit non-zero; direct CLI invocation with --all and no --ecosystem when host context is not detectable
```

Parsing failures inside a target skill are findings, not command-level fatal errors.

Forbidden interface shape:

- no `--api-key`
- no `--token`
- no `--endpoint`
- no `--service-url`
- no required environment variable for an external audit API

Any optional semantic or clustering enhancement must use:

- host-native capabilities exposed by Codex or Claude Code, or
- purely local deterministic analysis

It must not require a separate external API contract to be usable.

Default target resolution rules:

- wrapper invocation from Codex with `--all` and no explicit ecosystem override scans Codex skill roots only
- wrapper invocation from Claude Code with `--all` and no explicit ecosystem override scans Claude skill roots only
- direct CLI invocation outside a wrapper treats `host` as:
  - `codex` when Codex host context is detectable
  - `claude` when Claude host context is detectable
  - error `HOST_ECOSYSTEM_UNKNOWN` when host context is not detectable and no explicit `--ecosystem` is provided; the command exits non-zero with a message telling the user to pass `--ecosystem codex`, `--ecosystem claude`, or `--ecosystem both`
- explicit `--ecosystem both` is the only mode that scans both ecosystems in one run

### Shared audit design vs ecosystem-specific deltas

Shared design:

- skill discovery under one or more resolved roots
- `SKILL.md` parsing and common frontmatter validation
- normalized finding model
- deterministic vs heuristic result split
- ledger, index, cluster, and active-set persistence
- watch and git-hook execution model
- report rendering
- host-native usability with no standalone external API dependency

Codex-specific deltas:

- default host roots are under the Codex installation layout
- `agents/openai.yaml` is a first-class companion file
- Codex-specific rule set checks `openai.yaml` shape, UI metadata constraints, and referenced icon assets
- wrapper-triggered global audit scans Codex skills only unless explicitly overridden

Claude-specific deltas:

- default host roots are under the Claude Code installation and plugin layouts
- `compatibility` and Claude plugin path hints are first-class ecosystem signals
- Claude-specific rule set allows `compatibility` and checks Claude-only companion hints when present
- wrapper-triggered global audit scans Claude skills only unless explicitly overridden

Shared engine design requirement:

- common logic stays in one engine
- ecosystem-specific deltas must be declared explicitly in rules, root resolution, and companion-file parsing
- reports must label whether a finding comes from common logic or an ecosystem-specific delta
- host-enhanced logic must call through Codex or Claude Code native surfaces when available, and degrade to local-only behavior when unavailable
- the product must remain usable without any separately provisioned API key or external audit endpoint

### Common security and privacy constraints

These constraints apply to:

- `skill-auditor` repository content that ships as part of the audit package
- any audited skill content under the selected audit scope

Deterministic error patterns:

- hardcoded API keys, tokens, passwords, private keys, or equivalent secrets
- committed private or user-sensitive data that is not clearly synthetic or redacted
- hooks, scripts, or shell snippets that pipe network output directly into a shell
- hooks, scripts, or shell snippets that directly execute opaque binaries, downloaded artifacts, or temp/cache binaries from shell
- hook or script flows that require hidden local credentials files without declaring that dependency as an explicit contract

Allowed execution patterns:

- interpreter-first execution of committed, reviewable text scripts such as `python file.py`, `node file.mjs`, or `bash file.sh`
- explicit invocation of repository scripts when the target file is text, committed, and reviewable

Suspicious execution examples that must be flagged:

- `curl ... | bash`
- `wget ... -O - | sh`
- `./downloaded-tool`
- `bash ./binary-blob`
- executing binaries from temp, cache, or download paths without a reviewed wrapper contract

Reporting requirement:

- these findings are `deterministic_findings`
- these findings use `severity=error`
- any skill instance with an active finding from this constraint is excluded from the recommended active set

### Runtime entry: `skill-auditor hooks install`

```text
skill-auditor hooks install --repo <path>
  arg.--repo            path     required: target repository

success → hook scripts installed or updated; exit 0
error INVALID_ARGUMENT  → exit non-zero; path missing or invalid
error REPO_NOT_FOUND    → exit non-zero; target path is not a git repository
error INSTALL_FAILED    → exit non-zero; hook write failed
```

### Runtime entry: `skill-auditor watch`

```text
skill-auditor watch [path...]
  args.path              path[]   optional: skill dirs or roots to watch; defaults to same resolution as audit --all
  flag.--ecosystem       enum     optional: host/codex/claude/both
  flag.--format          enum     optional: text/json/markdown

success → watch loop starts; exits 0 only on clean shutdown (SIGINT or SIGTERM)
error INVALID_ARGUMENT      → exit non-zero; malformed flags or incompatible arguments
error TARGET_NOT_FOUND      → exit non-zero; no resolvable watch root
error HOST_ECOSYSTEM_UNKNOWN → exit non-zero; same condition as audit entry
```

Watch process lifecycle:

- starts a filesystem watcher on resolved skill roots
- on SIGINT or SIGTERM: flush any in-progress audit, write final state, exit 0
- on unhandled fatal exception: write a partial state marker if possible, exit non-zero with ENGINE_BROKEN
- running multiple watch processes against overlapping roots is allowed; each process operates independently and writes state atomically; no cross-process locking is required for the MVP
- a PID file or lock file is not required; watch processes do not prevent each other from running

### Persistent object: Skill instance record

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `instance_id` | string | yes | stable unique id for one installed copy |
| `skill_key` | string | yes | logical skill identity, usually frontmatter `name` |
| `ecosystem` | enum | yes | `codex / claude / unknown` |
| `path` | string | yes | canonical absolute path |
| `source_kind` | enum | yes | `user_root / plugin_marketplace / plugin_cache / git_clone / local_repo / manual_path / unknown` |
| `source` | object | yes | provenance fields; may be partial |
| `name` | string | yes | parsed frontmatter name or fallback |
| `description` | string | no | parsed frontmatter description when available |
| `fingerprint` | string | yes | hash of relevant content |
| `last_seen_at` | timestamp | yes | RFC 3339 |

### Persistent object: Finding

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `rule_id` | string | yes | stable rule identifier |
| `category` | enum | yes | `schema / structure / trigger / overlap / smell / lifecycle` |
| `severity` | enum | yes | `error / warn / info` |
| `confidence` | number | yes | deterministic = `1.0`; heuristic `< 1.0` |
| `ecosystem` | enum | yes | `codex / claude / unknown` |
| `instance_id` | string | yes | owning skill instance |
| `path` | string | yes | file or directory path |
| `evidence` | string | yes | human-readable proof |
| `suggested_fix` | string | no | direct next step |
| `line_number` | integer | no | source line where the finding was detected |
| `matched_text` | string | no | code snippet that triggered the finding (truncated to 120 chars) |

### Persistent object: Ledger entry

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `instance_id` | string | yes | ledger owner |
| `skill_key` | string | yes | logical skill identity |
| `note` | string | no | operator-maintained note |
| `updated_at` | timestamp | yes | last ledger write |
| `change_log` | array | yes | ledger-local maintenance history |
| `source` | object | yes | provenance snapshot |
| `source_kind` | enum | yes | same enum as skill instance |
| `audit_mode` | enum | yes | `manual / watch / git_hook / sync` |
| `last_audit_summary` | object | yes | summary counts and status |
| `last_fingerprint` | string | yes | last audited content hash |

### Ledger lifecycle

Creation: a ledger file is created on first audit of a skill instance. It is never created speculatively.

Write semantics per field:

- `note`: operator-maintained; never overwritten by automated audit. Automated audit reads it but must not modify it.
- `change_log`: append-only. Each audit appends a summary entry. Existing entries are never modified or removed.
- All other fields: last-write-wins on each audit run.

Prune conditions: a ledger file may only be deleted under one of the following conditions:

- the owning skill instance path no longer exists on disk and the user explicitly runs a future `skill-auditor prune` command (not yet implemented; tracked in checklist)
- the user explicitly requests removal of a specific instance ledger

No automated audit run may delete or truncate a ledger file. The `skill_index.json`, `clusters.json`, and `active_set.json` derived files may be rebuilt freely, but ledger files are not derived state.

### Persistent object: Audit run record

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | unique per audit |
| `status` | enum | yes | `running / completed / failed / skipped` |
| `target_scope` | object | yes | requested paths or `--all` |
| `deterministic_findings` | array | yes | normalized findings |
| `heuristic_findings` | array | yes | normalized findings |
| `semantic_status` | enum | yes | `not_requested / completed / skipped / failed` |
| `started_at` | timestamp | yes | RFC 3339 |
| `finished_at` | timestamp | no | RFC 3339 when terminal |

### Process object: `checklist.json` item

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string | yes | stable work item id |
| `title` | string | yes | short task name |
| `status` | enum | yes | `pending / in_progress / blocked / done` |
| `spec_delta` | bool | no | `true` when spec has changed for this area and the implementation has not yet caught up; omit or `false` otherwise |
| `spec_refs` | string[] | yes | affected `docs/spec/spec.md` sections |
| `notes` | string | no | execution note; when `spec_delta` is true, notes must describe what changed and what the implementation needs to do |

### Process object: `update_history` entry

`docs/spec/update_history` is an append-only canonical revision log file inside the spec package.

The canonical serialization format is **Markdown**. Each entry is a level-2 heading (`## vX.Y.Z — YYYY-MM-DD`) followed by bold-label fields. This format produces clean per-entry git diffs, renders naturally on GitHub, and satisfies the only tool-parsing need (cross-referencing version numbers by regex). Do not use JSON, JSON Lines, or JSON array format. Existing entries must never be modified or removed.

Entry template:

```markdown
## vX.Y.Z — YYYY-MM-DD

**Summary:** one-sentence description of the accepted change

**Rationale:** why the change was accepted

**Spec refs:** comma-separated list of affected spec.md sections

**Checklist ids:** comma-separated checklist item ids, or omit if none

---
```

| Field | Required | Notes |
|-------|----------|-------|
| version heading | yes | `## vX.Y.Z — YYYY-MM-DD` |
| Summary | yes | accepted change summary |
| Rationale | yes | why the change was accepted |
| Spec refs | yes | affected `docs/spec/spec.md` sections |
| Checklist ids | no | related checklist item ids |

### State machine: audit run status

```text
running   ──► completed   (audit and state writes succeed)
running   ──► failed      (fatal command-level error)
running   ──► skipped     (dedupe or watcher skip by unchanged fingerprint)
```

`completed`、`failed`、`skipped` are terminal.

### Filesystem layout

Relevant tree:

```text
Root: repository root

README.md
docs/
  spec/
    spec.md
    checklist.json
    update_history
    references.md
hooks/
skills/
src/skill_auditor/
tests/
```

Ownership rules:

| Path | Responsibility |
|------|----------------|
| `README.md` | project entrypoint |
| `docs/spec/spec.md` | canonical complete design |
| `docs/spec/checklist.json` | repository execution tracker |
| `docs/spec/update_history` | append-only design change log |
| `docs/spec/references.md` | committed reference analysis |
| `hooks/` | hook templates and install helpers |
| `src/skill_auditor/` | executable implementation |
| `skills/` | Codex and Claude wrapper skills |
| `tests/` | unit and integration tests |

Runtime output layout:

```text
Root: ~/.local/state/skill-auditor/

skill_index.json
clusters.json
active_set.json
skill_ledger/<instance_id>.json
audit_runs/<run_id>.json
```

Ownership rules:

| Path | Responsibility |
|------|----------------|
| `skill_index.json` | global discovered-skill index |
| `clusters.json` | overlap and duplicate clustering output |
| `active_set.json` | recommended auto-trigger set |
| `skill_ledger/<instance_id>.json` | per-instance maintenance record |
| `audit_runs/<run_id>.json` | immutable audit snapshot |

### Deletion and retention semantics

| Path or object | Model | Behavior |
|----------------|-------|----------|
| `docs/spec/spec.md` | rewrite-in-place | current accepted design only |
| `docs/spec/checklist.json` | rewrite-in-place | current execution status only |
| `docs/spec/update_history` | append-only | prior accepted changes remain |
| `skill_index.json` | rewrite-in-place | rebuilt after each audit |
| `clusters.json` | rewrite-in-place | rebuilt after cluster pass |
| `active_set.json` | rewrite-in-place | rebuilt after recommendation pass |
| `audit_runs/<run_id>.json` | hard delete allowed | disposable historical snapshots under retention policy |
| `skill_ledger/<instance_id>.json` | retain-until-forgotten | preserved until explicit prune/remove flow exists |

### Cross-system write order

One audit run that updates state must write in this order:

1. read and fingerprint target skill instances
2. compute deterministic findings
3. compute optional heuristic findings
4. write `audit_runs/<run_id>.json`
5. update affected `skill_ledger/<instance_id>.json`
6. rebuild `skill_index.json`
7. rebuild `clusters.json` and `active_set.json` when required
8. print final summary and exit status

Invalid input, missing target paths, broken CLI preconditions, and state write failures abort the command with named errors. They do not silently report success.

## Failure Cases and Acceptance

Capability: deterministic schema audit is correct for required common rules
  Failure example: a skill missing frontmatter is reported as clean
  Expected: the instance gets an `error` finding with direct evidence
  Completion signal: missing-frontmatter false-negative count = 0 in the schema fixture matrix

Capability: Codex-only and Claude-only hard rules never cross-fire
  Failure example: a Claude skill is blocked because it lacks `agents/openai.yaml`
  Expected: Codex-specific hard rules apply only to Codex skills or Codex-specific companion files
  Completion signal: cross-ecosystem hard-failure count = 0 in the mixed-ecosystem fixture matrix

Capability: secrets and private data are hard-failed
  Failure example: a skill or audit package file contains a real API key, private token, password, or non-redacted private user data
  Expected: the audit emits an `error` finding with direct evidence and the affected instance is excluded from the recommended active set
  Completion signal: secret-and-privacy false-negative count = 0 in the sensitive-fixture matrix

Capability: the tool is directly usable from Codex and Claude Code without external API configuration
  Failure example: running the auditor requires setting a separate API key or configuring a standalone audit endpoint before any audit can run
  Expected: deterministic audit works with host-native context only; optional semantic analysis degrades to `skipped` when host-native capabilities are unavailable
  Completion signal: external-api-required count = 0 in the host-setup fixture matrix

Capability: global audit defaults to the current host ecosystem only
  Failure example: running global audit from Codex also scans Claude skills without an explicit cross-ecosystem request
  Expected: host-default audit scope resolves to Codex in Codex, Claude in Claude Code, and scans both only under explicit override
  Completion signal: host-default cross-scan count = 0 in the host-context fixture matrix

Capability: suspicious shell and binary execution patterns are hard-failed
  Failure example: a hook runs `curl ... | bash` or executes an opaque downloaded binary directly from shell
  Expected: the audit emits an `error` finding with the suspicious command pattern as evidence
  Completion signal: suspicious-shell-binary false-negative count = 0 in the execution-pattern fixture matrix

Capability: watch mode audits only relevant skill changes
  Failure example: editing an unrelated file triggers a duplicate audit
  Expected: only changes under owned skill files map to audits, and unchanged fingerprints are skipped
  Completion signal: duplicate-watch-audit count = 0 in the watch debounce test matrix

Capability: git hooks block only deterministic errors
  Failure example: a heuristic overlap warning blocks commit
  Expected: commit or push is blocked only when deterministic `error` findings exist
  Completion signal: heuristic-only block count = 0 in the hook fixture matrix

Capability: active-set recommendation respects the configured cap
  Failure example: the recommender outputs 31 active skills when max is 30
  Expected: `recommended_active` length never exceeds configured `max`
  Completion signal: active-set overflow count = 0 across recommendation tests

Capability: duplicate and overlap analysis keeps logical identity and installed copies separate
  Failure example: two installed copies of one skill are collapsed into one instance record
  Expected: the system preserves distinct `instance_id` values while grouping them under one `skill_key` or cluster
  Completion signal: duplicate-instance merge error count = 0 in clustering tests

## Implementation Phases or Rollout Steps

Phase 1: repository control files and runtime state contracts
  Includes: `docs/spec/spec.md` canonicalization, `docs/spec/checklist.json` schema, `docs/spec/update_history` schema, runtime state path contract
  Done when: repository and runtime ownership rules are represented in tests and no path-purpose ambiguity remains
  Blocks: parser and state-writing implementation depend on the runtime contract

Phase 2: discovery, ecosystem detection, and deterministic parsing
  Includes: host-aware root scanning, skill root detection, frontmatter parsing, companion-file discovery, common/Codex/Claude hard rules, and security/privacy execution-pattern checks
  Done when: mixed fixture roots produce stable instance inventories, host-default scans stay within the current ecosystem, secrets/privacy and suspicious execution patterns are hard-failed, and deterministic findings stay stable across repeated runs
  Blocks: reporting and hooks depend on normalized findings

Phase 3: ledger, index, and report generation
  Includes: normalized finding model, audit run records, per-skill ledger writes, global index rebuild, text/json/markdown outputs
  Done when: one audit run writes all required state files in the declared order and outputs the same summary across repeated runs
  Blocks: clustering and recommendation depend on persisted normalized state

Phase 4: watch mode and git-hook gate
  Includes: file change mapping, debounce, fingerprint skip, hook installer, deterministic block policy
  Done when: watch mode ignores unrelated edits and git hooks block only deterministic error findings
  Blocks: semantic analysis is independent; active-set refresh depends on audit completion

Phase 5: overlap analysis, active-set recommendation, and optional semantic pass
  Includes: lexical overlap scoring, normalized summaries, optional host-native review, recommendation ranking and cap enforcement
  Done when: duplicate/overlap fixtures cluster correctly, host-native semantic-unavailable runs degrade to `skipped`, no external API setup is required, and recommended sets never exceed the configured cap
  Blocks: none; this phase completes the v1 surface

## References

### `docs/spec/references.md`

What it contributes: extracted common rules, Codex-only rules, Claude-only rules, and the required separation between deterministic and heuristic checks.
Maps to: `Ownership or Source of Truth`, `Core Decisions`, `Data and Interface Contracts`

### OpenAI Codex skill-creator reference

What it contributes: `SKILL.md` hard validation rules, `agents/openai.yaml` expectations, and concise skill-structure guidance.
Maps to: `Data and Interface Contracts`, `Failure Cases and Acceptance`

### Anthropic skill-creator reference

What it contributes: optional `compatibility`, eval-oriented thinking, packaging exclusions, and description-trigger optimization cues.
Maps to: `Data and Interface Contracts`, `Core Decisions`, `Implementation Phases or Rollout Steps`
