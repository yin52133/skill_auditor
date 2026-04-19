# skill-auditor Specification

## Problem and Goal

Codex 和 Claude Code 的 skill 集合会长期积累重复、过期、误触发和结构不合规的问题。当前缺少一个统一工具，能跨两套生态做客观审计、归类、维护记录和自动审计触发。这个设计定义 `skill-auditor`：一个共享 Python 内核、双生态薄包装、静态硬校验与启发式分析分层、并带维护账本与 active-set 推荐的技能审计系统。`docs/spec/spec.md` 是当前完整设计；`docs/spec/checklist.json` 和 `docs/spec/update_history` 负责后续实现进度与设计变更记录。

## Scope and Non-Goals

In scope:

- 扫描 `~/.codex/skills`、`~/.claude/skills` 及可识别插件 skill 根目录
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
                  ├── reads ──► installed skill roots
                  │               (~/.codex/... , ~/.claude/...)
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
run optional semantic analysis
  │
  ├── backend unavailable? ──► mark semantic_status=skipped
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
  flag.--all             bool     optional: scan default installed roots
  flag.--format          enum     optional: text/json/markdown
  flag.--ecosystem       enum     optional: codex/claude/unknown

success → audit report emitted; exit 0 when no deterministic error blocks the requested mode
error INVALID_ARGUMENT → exit non-zero; malformed flags or incompatible arguments
error TARGET_NOT_FOUND  → exit non-zero; no matching skill instance under requested target
error STATE_WRITE_FAILED → exit non-zero; report computed but runtime state write failed
error ENGINE_BROKEN     → exit non-zero; internal invariant or unexpected fatal exception
```

Parsing failures inside a target skill are findings, not command-level fatal errors.

### Runtime entry: `skill-auditor hooks install`

```text
skill-auditor hooks install --repo <path>
  arg.--repo            path     required: target repository

success → hook scripts installed or updated; exit 0
error INVALID_ARGUMENT  → exit non-zero; path missing or invalid
error REPO_NOT_FOUND    → exit non-zero; target path is not a git repository
error INSTALL_FAILED    → exit non-zero; hook write failed
```

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
| `spec_refs` | string[] | yes | affected `docs/spec/spec.md` sections |
| `notes` | string | no | execution note |

### Process object: `update_history` entry

`docs/spec/update_history` is an append-only canonical revision log file inside the spec package.

The implementation may serialize it as JSON, JSON Lines, or Markdown with machine-readable frontmatter. The required contract is the record content, not the encoding.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `version` | string | yes | design revision version, default format `major.minor.patch` |
| `date` | string | yes | `YYYY-MM-DD` |
| `summary` | string | yes | accepted change summary |
| `rationale` | string | yes | why the change was accepted |
| `spec_refs` | string[] | yes | affected `docs/spec/spec.md` sections |
| `checklist_ids` | string[] | no | related checklist item ids |

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
  Includes: root scanning, skill root detection, frontmatter parsing, companion-file discovery, common/Codex/Claude hard rules
  Done when: mixed fixture roots produce stable instance inventories and deterministic findings across repeated runs
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
  Includes: lexical overlap scoring, normalized summaries, optional model-backed review, recommendation ranking and cap enforcement
  Done when: duplicate/overlap fixtures cluster correctly, semantic-unavailable runs degrade to `skipped`, and recommended sets never exceed the configured cap
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
