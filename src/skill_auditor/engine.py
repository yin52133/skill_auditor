from __future__ import annotations

import json
from pathlib import Path

from .analysis import build_overlap_findings, build_trigger_findings
from .discovery import resolve_targets
from .frontmatter import parse_skill_markdown
from .models import AuditReport, SkillInstance
from .rules import validate_instance
from .state import StateManager
from .utils import compute_directory_fingerprint, make_instance_id, make_run_id, utc_now


def _build_instance(target) -> SkillInstance:
    skill_dir = Path(target.path)
    parsed = parse_skill_markdown(skill_dir / "SKILL.md")
    metadata = parsed.metadata or {}
    name = metadata.get("name") if isinstance(metadata.get("name"), str) else skill_dir.name
    description = metadata.get("description") if isinstance(metadata.get("description"), str) else None
    return SkillInstance(
        instance_id=make_instance_id(target.ecosystem, skill_dir),
        skill_key=name,
        ecosystem=target.ecosystem,
        path=str(skill_dir),
        source_kind=target.source_kind,
        source=target.source,
        name=name,
        description=description,
        fingerprint=compute_directory_fingerprint(skill_dir),
        last_seen_at=utc_now(),
    )


def run_audit(
    *,
    paths: list[str],
    use_all: bool,
    ecosystem_request: str | None,
    output_format: str,
    active_set_max: int,
    audit_mode: str,
    write_state: bool = True,
    include_heuristics: bool = True,
) -> tuple[AuditReport, int]:
    started_at = utc_now()
    targets = resolve_targets(paths, use_all=use_all, ecosystem_request=ecosystem_request)
    instances = [_build_instance(target) for target in targets]
    instances.sort(key=lambda item: (item.skill_key, item.path))

    deterministic_findings = []
    state = StateManager()
    for instance in instances:
        rule_exceptions: list[str] = []
        ledger_path = state.state_root / "skill_ledger" / f"{instance.instance_id}.json"
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            rule_exceptions = ledger.get("rule_exceptions", [])
        deterministic_findings.extend(validate_instance(instance, rule_exceptions=rule_exceptions))
    deterministic_findings.sort(key=lambda item: (item.severity, item.rule_id, item.path))

    heuristic_findings = []
    if include_heuristics:
        heuristic_findings.extend(build_overlap_findings(instances))
        heuristic_findings.extend(build_trigger_findings(instances))
    heuristic_findings.sort(key=lambda item: (item.rule_id, item.path))

    report = AuditReport(
        run_id=make_run_id(),
        status="completed",
        target_scope={"paths": paths, "all": use_all, "ecosystem": ecosystem_request or "host"},
        instances=instances,
        deterministic_findings=deterministic_findings,
        heuristic_findings=heuristic_findings,
        semantic_status="skipped",
        started_at=started_at,
        finished_at=utc_now(),
    )

    if write_state:
        state.write(report, audit_mode=audit_mode, active_set_max=active_set_max)

    exit_code = 1 if any(finding.severity == "error" for finding in deterministic_findings) else 0
    return report, exit_code
