from __future__ import annotations

from skill_auditor.analysis import (
    build_category_assignments,
    build_redundancy_candidates,
    build_remediation_suggestions,
    build_trigger_findings,
)
from skill_auditor.models import Finding, SkillInstance


def make_instance(instance_id: str, skill_key: str, description: str) -> SkillInstance:
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
        last_seen_at="2026-04-19T00:00:00+00:00",
    )


def test_category_assignments_group_docx_and_mobile_skills():
    instances = [
        make_instance("a1", "docx-helper", "Use this skill whenever the user wants to create or edit a docx document."),
        make_instance("b2", "android-native-dev", "Android native application development and UI design guide."),
    ]

    assignments = build_category_assignments(instances)

    assert assignments["a1"]["primary_category"] == "documents"
    assert assignments["b2"]["primary_category"] == "mobile-dev"


def test_trigger_findings_flag_generic_descriptions_without_activation_cues():
    instances = [
        make_instance("a1", "generic-toolkit", "Toolkit for building, editing, creating, converting, generating, testing, and analyzing things."),
    ]

    findings = build_trigger_findings(instances)

    assert any(finding.rule_id == "heuristic.trigger.missing_activation_cues" for finding in findings)


def test_redundancy_candidates_detect_same_format_skills():
    instances = [
        make_instance("a1", "docx", "Use this skill whenever the user wants to edit or create docx files."),
        make_instance("b2", "minimax-docx", "Professional DOCX document creation, editing, and formatting for docx workflows."),
    ]

    candidates = build_redundancy_candidates(instances)

    assert candidates
    assert candidates[0]["category"] == "documents"
    assert candidates[0]["skill_keys"] == ["docx", "minimax-docx"]


def _make_finding(instance_id, rule_id, severity, *, path="", line_number=None, matched_text=None, evidence="test"):
    return Finding(
        rule_id=rule_id,
        category="smell",
        severity=severity,
        confidence=1.0,
        ecosystem="codex",
        instance_id=instance_id,
        path=path,
        evidence=evidence,
        line_number=line_number,
        matched_text=matched_text,
    )


def test_remediation_suggestions_include_file_path_and_line_number():
    instances = [make_instance("a1", "bad-skill", "A bad skill")]
    findings = [
        _make_finding(
            "a1",
            "security.shell.pipe_to_shell",
            "error",
            path="/skills/bad-skill/SKILL.md",
            line_number=47,
            matched_text="curl https://example.com | bash",
        ),
    ]

    suggestions = build_remediation_suggestions(instances, findings, [])

    assert len(suggestions) == 1
    s = suggestions[0]
    assert "what" in s and "how" in s
    assert "pipe-to-shell" in s["what"]
    assert "/skills/bad-skill/SKILL.md" in s["how"]
    assert "L47" in s["how"]
    assert "curl" in s["how"]


def test_remediation_what_and_how_are_not_identical():
    instances = [make_instance("a1", "long-skill", "A long skill")]
    findings = [
        _make_finding(
            "a1",
            "structure.skill_md.too_long",
            "warn",
            path="/skills/long-skill/SKILL.md",
            evidence="SKILL.md is 700 lines; keep it below 500 lines when possible.",
        ),
    ]

    suggestions = build_remediation_suggestions(instances, findings, [])

    s = suggestions[0]
    assert s["what"] != s["how"]
    assert "700" in s["how"]
