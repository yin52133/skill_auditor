from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ResolvedSkillTarget:
    path: str
    ecosystem: str
    source_kind: str
    source: dict[str, Any]


@dataclass(slots=True)
class ParsedSkill:
    metadata: dict[str, Any] | None
    body: str
    errors: list[tuple[str, str]]
    raw_content: str


@dataclass(slots=True)
class SourceRecord:
    source_kind: str
    remote_url: str | None = None
    remote_ref: str | None = None
    remote_commit: str | None = None
    last_synced_at: str | None = None
    sync_protected: bool = False
    tags: list[str] = field(default_factory=list)
    rule_exceptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkillInstance:
    instance_id: str
    skill_key: str
    ecosystem: str
    path: str
    source_kind: str
    source: dict[str, Any]
    name: str
    description: str | None
    fingerprint: str
    last_seen_at: str
    sync_protected: bool = False
    tags: list[str] = field(default_factory=list)
    rule_exceptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Finding:
    rule_id: str
    category: str
    severity: str
    confidence: float
    ecosystem: str
    instance_id: str
    path: str
    evidence: str
    suggested_fix: str | None = None
    line_number: int | None = None
    matched_text: str | None = None


@dataclass(slots=True)
class AuditReport:
    run_id: str
    status: str
    target_scope: dict[str, Any]
    instances: list[SkillInstance]
    deterministic_findings: list[Finding]
    heuristic_findings: list[Finding]
    semantic_status: str
    started_at: str
    finished_at: str


@dataclass(slots=True)
class WatchAction:
    action: str
    skill_dir: str
    reason: str


@dataclass(slots=True)
class HookCheckResult:
    block: bool
    error_count: int
    impacted_skill_dirs: list[str]
    findings: list[Finding]


@dataclass(slots=True)
class BatchEditResult:
    applied: list[str]
    skipped_protected: list[str]
    skipped_builtin: list[str]
    skipped_missing: list[str]
    failed: list[tuple[str, str]]


@dataclass(slots=True)
class UpgradeCandidate:
    instance_id: str
    skill_key: str
    path: str
    current_ref: str | None
    current_commit: str | None
    remote_url: str | None
    remote_ref: str | None
    remote_commit: str | None
    changed_files: list[str]
    diff_summary: str
