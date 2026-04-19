from __future__ import annotations

import json
from pathlib import Path

from skill_auditor.models import AuditReport, Finding, SkillInstance
from skill_auditor.state import StateManager


def _make_instance(instance_id="i1", skill_key="my-skill", **kw) -> SkillInstance:
    defaults = dict(
        instance_id=instance_id,
        skill_key=skill_key,
        ecosystem="codex",
        path=f"/skills/{skill_key}",
        source_kind="user_root",
        source={"requested_path": "/skills"},
        name=skill_key,
        description="A test skill",
        fingerprint=f"fp-{instance_id}",
        last_seen_at="2026-04-20T00:00:00+00:00",
    )
    defaults.update(kw)
    return SkillInstance(**defaults)


def _make_report(instances=None, det_findings=None, heur_findings=None, **kw) -> AuditReport:
    defaults = dict(
        run_id="run-001",
        status="completed",
        target_scope={"roots": ["/skills"]},
        instances=instances or [],
        deterministic_findings=det_findings or [],
        heuristic_findings=heur_findings or [],
        semantic_status="clean",
        started_at="2026-04-20T00:00:00+00:00",
        finished_at="2026-04-20T00:01:00+00:00",
    )
    defaults.update(kw)
    return AuditReport(**defaults)


def _make_finding(instance_id, rule_id="test.rule", severity="warn") -> Finding:
    return Finding(
        rule_id=rule_id,
        category="smell",
        severity=severity,
        confidence=1.0,
        ecosystem="codex",
        instance_id=instance_id,
        path="/skills/test/SKILL.md",
        evidence="test evidence",
    )


def test_state_root_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path / "custom"))
    state = StateManager()
    assert state.state_root == tmp_path / "custom"


def test_write_creates_audit_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    run_file = tmp_path / "audit_runs" / "run-001.json"
    assert run_file.exists()
    data = json.loads(run_file.read_text())
    assert data["run_id"] == "run-001"
    assert len(data["instances"]) == 1


def test_write_creates_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    ledger_file = tmp_path / "skill_ledger" / "i1.json"
    assert ledger_file.exists()
    ledger = json.loads(ledger_file.read_text())
    assert ledger["skill_key"] == "my-skill"
    assert ledger["last_audit_summary"]["status"] == "clean"


def test_ledger_preserves_tags_and_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    ledger_dir = tmp_path / "skill_ledger"
    ledger_dir.mkdir(parents=True)
    existing = {
        "instance_id": "i1",
        "tags": ["reviewed"],
        "note": "important skill",
        "rule_exceptions": ["test.rule"],
        "sync_protected": True,
    }
    (ledger_dir / "i1.json").write_text(json.dumps(existing))

    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    ledger = json.loads((ledger_dir / "i1.json").read_text())
    assert ledger["tags"] == ["reviewed"]
    assert ledger["note"] == "important skill"
    assert ledger["rule_exceptions"] == ["test.rule"]
    assert ledger["sync_protected"] is True


def test_ledger_counts_errors_and_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    findings = [
        _make_finding("i1", severity="error"),
        _make_finding("i1", severity="error"),
        _make_finding("i1", severity="warn"),
    ]
    report = _make_report(instances=[inst], det_findings=findings)
    state.write(report, audit_mode="full", active_set_max=10)

    ledger = json.loads((tmp_path / "skill_ledger" / "i1.json").read_text())
    assert ledger["last_audit_summary"]["error_count"] == 2
    assert ledger["last_audit_summary"]["warn_count"] == 1
    assert ledger["last_audit_summary"]["status"] == "blocked"


def test_write_creates_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    index_file = tmp_path / "skill_index.json"
    assert index_file.exists()
    data = json.loads(index_file.read_text())
    assert len(data["instances"]) == 1


def test_write_creates_clusters(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    clusters_file = tmp_path / "clusters.json"
    assert clusters_file.exists()


def test_write_creates_active_set(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()
    report = _make_report(instances=[inst])
    state.write(report, audit_mode="full", active_set_max=10)

    active_set_file = tmp_path / "active_set.json"
    assert active_set_file.exists()


def test_ledger_change_log_appends(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    inst = _make_instance()

    report1 = _make_report(run_id="run-001", instances=[inst])
    state.write(report1, audit_mode="full", active_set_max=10)

    report2 = _make_report(run_id="run-002", instances=[inst])
    state.write(report2, audit_mode="full", active_set_max=10)

    ledger = json.loads((tmp_path / "skill_ledger" / "i1.json").read_text())
    assert len(ledger["change_log"]) == 2
    assert ledger["change_log"][0]["run_id"] == "run-001"
    assert ledger["change_log"][1]["run_id"] == "run-002"
