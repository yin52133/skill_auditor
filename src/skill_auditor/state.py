from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from .analysis import build_active_set, build_clusters
from .models import AuditReport, Finding, SkillInstance
from .utils import atomic_write_json, utc_now


class StateManager:
    def __init__(self, state_root: Path | None = None):
        root = state_root or Path(os.environ.get("SKILL_AUDITOR_STATE_ROOT", "~/.local/state/skill-auditor"))
        self.state_root = root.expanduser()

    def write(
        self,
        report: AuditReport,
        *,
        audit_mode: str,
        active_set_max: int,
    ) -> None:
        self._write_audit_run(report)
        for instance in report.instances:
            self._update_ledger(instance, report, audit_mode=audit_mode)
        self._write_index(report.instances)
        self._write_clusters(report.instances)
        self._write_active_set(
            report.instances,
            report.deterministic_findings,
            report.heuristic_findings,
            max_items=active_set_max,
        )

    def _write_audit_run(self, report: AuditReport) -> None:
        payload = {
            "run_id": report.run_id,
            "status": report.status,
            "target_scope": report.target_scope,
            "instances": [asdict(instance) for instance in report.instances],
            "deterministic_findings": [asdict(finding) for finding in report.deterministic_findings],
            "heuristic_findings": [asdict(finding) for finding in report.heuristic_findings],
            "semantic_status": report.semantic_status,
            "started_at": report.started_at,
            "finished_at": report.finished_at,
        }
        atomic_write_json(self.state_root / "audit_runs" / f"{report.run_id}.json", payload)

    def _update_ledger(self, instance: SkillInstance, report: AuditReport, *, audit_mode: str) -> None:
        ledger_path = self.state_root / "skill_ledger" / f"{instance.instance_id}.json"
        existing = {}
        if ledger_path.exists():
            existing = json.loads(ledger_path.read_text(encoding="utf-8"))

        note = existing.get("note")
        change_log = list(existing.get("change_log", []))
        instance_findings = [finding for finding in report.deterministic_findings if finding.instance_id == instance.instance_id]
        error_count = sum(1 for finding in instance_findings if finding.severity == "error")
        warn_count = sum(1 for finding in instance_findings if finding.severity == "warn")
        change_log.append(
            {
                "run_id": report.run_id,
                "updated_at": report.finished_at,
                "audit_mode": audit_mode,
                "error_count": error_count,
                "warn_count": warn_count,
            }
        )

        payload = {
            "instance_id": instance.instance_id,
            "skill_key": instance.skill_key,
            "updated_at": report.finished_at,
            "change_log": change_log,
            "source": instance.source,
            "source_kind": instance.source_kind,
            "audit_mode": audit_mode,
            "last_audit_summary": {
                "error_count": error_count,
                "warn_count": warn_count,
                "heuristic_count": sum(
                    1 for finding in report.heuristic_findings if finding.instance_id == instance.instance_id
                ),
                "status": "blocked" if error_count else "clean",
            },
            "last_fingerprint": instance.fingerprint,
        }
        if note is not None:
            payload["note"] = note
        atomic_write_json(ledger_path, payload)

    def _write_index(self, instances: list[SkillInstance]) -> None:
        payload = {
            "updated_at": utc_now(),
            "instances": [asdict(instance) for instance in instances],
        }
        atomic_write_json(self.state_root / "skill_index.json", payload)

    def _write_clusters(self, instances: list[SkillInstance]) -> None:
        payload = build_clusters(instances)
        payload["updated_at"] = utc_now()
        atomic_write_json(self.state_root / "clusters.json", payload)

    def _write_active_set(
        self,
        instances: list[SkillInstance],
        deterministic_findings: list[Finding],
        heuristic_findings: list[Finding],
        *,
        max_items: int,
    ) -> None:
        payload = build_active_set(instances, deterministic_findings, heuristic_findings, max_items=max_items)
        payload["updated_at"] = utc_now()
        atomic_write_json(self.state_root / "active_set.json", payload)
