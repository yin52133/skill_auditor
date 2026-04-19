from __future__ import annotations

import json

from skill_auditor.models import AuditReport, Finding, SkillInstance
from skill_auditor.reporting import render_report, render_json, render_text, render_markdown, build_report_summary


def _inst(instance_id="i1", skill_key="test-skill", description="A well-described test skill for auditing.") -> SkillInstance:
    return SkillInstance(
        instance_id=instance_id,
        skill_key=skill_key,
        ecosystem="codex",
        path=f"/skills/{skill_key}",
        source_kind="user_root",
        source={"requested_path": "/skills"},
        name=skill_key,
        description=description,
        fingerprint=f"fp-{instance_id}",
        last_seen_at="2026-04-20T00:00:00+00:00",
    )


def _report(instances=None, det=None, heur=None) -> AuditReport:
    return AuditReport(
        run_id="run-test",
        status="completed",
        target_scope={"ecosystem": "codex", "roots": ["/skills"]},
        instances=instances or [_inst()],
        deterministic_findings=det or [],
        heuristic_findings=heur or [],
        semantic_status="clean",
        started_at="2026-04-20T00:00:00+00:00",
        finished_at="2026-04-20T00:01:00+00:00",
    )


def _finding(instance_id="i1", rule_id="test.rule", severity="warn") -> Finding:
    return Finding(
        rule_id=rule_id, category="smell", severity=severity, confidence=1.0,
        ecosystem="codex", instance_id=instance_id, path="/skills/test/SKILL.md",
        evidence="test evidence",
    )


def test_render_json_is_valid_json():
    report = _report()
    result = render_json(report)
    data = json.loads(result)
    assert data["run_id"] == "run-test"
    assert "instances" in data
    assert "summary" in data


def test_render_text_contains_key_info():
    report = _report()
    result = render_text(report)
    assert "run-test" in result
    assert "test-skill" in result
    assert "instances: 1" in result


def test_render_text_zh_has_title():
    report = _report()
    result = render_text(report, language="zh")
    assert "审计报告" in result


def test_render_markdown_has_sections():
    report = _report()
    result = render_markdown(report)
    assert "# skill-auditor report" in result
    assert "## Executive Summary" in result
    assert "## Severity Summary" in result
    assert "## Active Set Recommendation" in result


def test_render_markdown_zh_has_chinese_sections():
    report = _report()
    result = render_markdown(report, language="zh")
    assert "审计报告" in result
    assert "总体摘要" in result


def test_render_report_dispatches_format():
    report = _report()
    assert "run_id" in render_report(report, "json")
    assert "run-test" in render_report(report, "text")
    assert "# skill-auditor report" in render_report(report, "markdown")


def test_build_report_summary_keys():
    report = _report()
    summary = build_report_summary(report)
    assert "validity" in summary
    assert "compliance" in summary
    assert "categories" in summary
    assert "trigger_quality" in summary
    assert "redundancy_candidates" in summary
    assert "governance_actions" in summary
    assert "priority_actions" in summary
    assert "remediation_suggestions" in summary
    assert "merge_suggestions" in summary


def test_render_markdown_with_findings():
    findings = [_finding(severity="error"), _finding(rule_id="other.rule", severity="warn")]
    report = _report(det=findings)
    result = render_markdown(report)
    assert "`error`: `1`" in result
    assert "`warn`: `1`" in result
    assert "Deterministic Findings" in result
