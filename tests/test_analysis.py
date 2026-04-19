from __future__ import annotations

from skill_auditor.analysis import (
    build_category_assignments,
    build_compliance_summary,
    build_merge_suggestions,
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


def test_merge_suggestions_detect_same_format_pair():
    instances = [
        make_instance("a1", "pdf", "Use this skill to create, read, merge PDF files."),
        make_instance("b2", "minimax-pdf", "Professional PDF creation with design tokens and templates."),
    ]
    suggestions = build_merge_suggestions(instances, [], [])
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["merge_type"] == "true_duplicate"
    assert set(s["merge_group"]) == {"pdf", "minimax-pdf"}


def test_merge_suggestions_family_consolidate():
    instances = [
        make_instance("a1", "pptx", "Create and edit pptx presentations."),
        make_instance("b2", "pptx-generator", "Generate pptx slide decks from outlines."),
        make_instance("c3", "slide-making-skill", "Build pptx presentations with templates."),
    ]
    suggestions = build_merge_suggestions(instances, [], [])
    family = [s for s in suggestions if s["merge_type"] == "family_consolidate"]
    assert len(family) == 1
    assert len(family[0]["merge_group"]) == 3


def test_merge_suggestions_pair_extracted_from_large_group():
    instances = [
        make_instance("a1", "pdf", "Create and merge PDF files."),
        make_instance("b2", "minimax-pdf", "Professional PDF design and creation."),
        make_instance("c3", "docx", "Create docx and export to pdf format."),
    ]
    suggestions = build_merge_suggestions(instances, [], [])
    pairs = [s for s in suggestions if s["merge_type"] == "true_duplicate"]
    assert any(set(p["merge_group"]) == {"pdf", "minimax-pdf"} for p in pairs)


def test_description_too_short_triggers_heuristic():
    instances = [make_instance("a1", "tiny-skill", "Short desc.")]
    findings = build_trigger_findings(instances)
    assert any(f.rule_id == "heuristic.header.description_too_short" for f in findings)


def test_compliance_summary_counts_missing_license():
    instances = [
        make_instance("a1", "good-skill", "A well-described skill for testing."),
        make_instance("b2", "bad-skill", "Another well-described skill for testing."),
    ]
    det_findings = [
        _make_finding("b2", "schema.frontmatter.missing_license", "warn"),
    ]
    summary = build_compliance_summary(instances, det_findings, [])
    assert summary["missing_license"] == 1
    assert summary["total"] == 2
