from __future__ import annotations

from skill_auditor.analysis import (
    build_active_set,
    build_governance_actions,
    build_priority_actions,
    build_remediation_suggestions,
    _active_score,
    _active_reasons,
    _would_duplicate_redundant_family,
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


def make_finding(instance_id: str, rule_id: str, *, category: str, severity: str, evidence: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=1.0 if severity == "error" else 0.7,
        ecosystem="codex",
        instance_id=instance_id,
        path=f"/skills/{instance_id}",
        evidence=evidence,
        suggested_fix=None,
    )


def test_governance_actions_include_invalid_redundancy_and_trigger_tracks():
    instances = [
        make_instance("a1", "docx", "Use this skill whenever the user wants to edit or create docx files."),
        make_instance("b2", "minimax-docx", "Professional DOCX document creation, editing, and formatting for docx workflows."),
        make_instance("c3", "theme-factory", "Toolkit for styling artifacts with a theme."),
    ]
    deterministic = [
        make_finding(
            "a1",
            "codex.openai_yaml.icon_small_missing",
            category="structure",
            severity="error",
            evidence="icon_small references missing asset ./assets/icon.svg.",
        )
    ]
    heuristic = [
        make_finding(
            "c3",
            "heuristic.trigger.missing_activation_cues",
            category="trigger",
            severity="warn",
            evidence="theme-factory reads like a generic capability summary without clear activation cues.",
        )
    ]

    actions = build_governance_actions(instances, deterministic, heuristic)

    action_types = {action["type"] for action in actions}
    assert "invalid-repair" in action_types
    assert "redundancy-review" in action_types
    assert "trigger-cleanup" in action_types


def test_active_set_prefers_diversity_over_redundant_same_category_pairs():
    instances = [
        make_instance("a1", "docx", "Use this skill whenever the user wants to edit or create docx files."),
        make_instance("b2", "minimax-docx", "Professional DOCX document creation, editing, and formatting for docx workflows."),
        make_instance("c3", "pdf", "Use this skill whenever the user wants to do anything with PDF files."),
        make_instance("d4", "webapp-testing", "Toolkit for interacting with and testing local web applications using Playwright."),
    ]

    active_set = build_active_set(instances, [], [], max_items=3)
    entries = active_set["recommended_active"]
    skill_keys = [entry["skill_key"] for entry in entries]

    assert "webapp-testing" in skill_keys
    assert {"docx", "minimax-docx"} & set(skill_keys)
    assert not {"docx", "minimax-docx"}.issubset(set(skill_keys))
    assert all("score" in entry and entry["score"] > 0 for entry in entries)
    assert all(entry["reasons"] for entry in entries)


# --- governance action edge cases ---

def test_governance_no_invalid_action_for_clean():
    instances = [make_instance("a1", "clean", "Use this when creating docx files")]
    actions = build_governance_actions(instances, [], [])
    assert not any(a["type"] == "invalid-repair" for a in actions)


# --- priority actions ---

def test_priority_p0_for_security_findings():
    instances = [make_instance("a1", "shell", "A skill")]
    findings = [make_finding("a1", "security.shell.pipe_to_shell", category="smell", severity="error", evidence="pipe to shell")]
    actions = build_priority_actions(instances, findings, [])
    p0 = [a for a in actions if a["priority"] == "P0"]
    assert len(p0) == 1
    assert "unsafe" in p0[0]["what"].lower()


def test_priority_empty_for_clean_instances():
    instances = [make_instance("a1", "clean", "Use this for docx")]
    actions = build_priority_actions(instances, [], [])
    assert len(actions) == 0


# --- remediation ---

def test_remediation_returns_empty_for_clean():
    instances = [make_instance("a1", "clean", "Use this when creating docx files")]
    suggestions = build_remediation_suggestions(instances, [], [])
    assert len(suggestions) == 0


def test_remediation_has_what_and_how():
    instances = [make_instance("a1", "bad", "A bad skill")]
    findings = [make_finding("a1", "schema.frontmatter.missing_name", category="schema", severity="error", evidence="missing name")]
    suggestions = build_remediation_suggestions(instances, findings, [])
    assert len(suggestions) == 1
    assert "what" in suggestions[0]
    assert "how" in suggestions[0]


# --- _active_score and _active_reasons ---

def test_active_score_returns_number(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    score = _active_score(repo_category_count=1, warning_count=0, heuristic_count=0, redundancy_penalty=0)
    assert isinstance(score, int)
    assert score == 100


# --- _would_duplicate_redundant_family ---

def test_would_duplicate_true_for_same_family():
    from skill_auditor.analysis import build_redundancy_candidates
    instances = [
        make_instance("a1", "docx", "Use this skill whenever the user wants to edit or create docx files."),
        make_instance("b2", "minimax-docx", "Professional DOCX document creation, editing, and formatting for docx workflows."),
    ]
    redundancy_candidates = build_redundancy_candidates(instances)
    assert _would_duplicate_redundant_family(instances[1], {"docx"}, redundancy_candidates) is True


def test_would_duplicate_false_for_different_family():
    from skill_auditor.analysis import build_redundancy_candidates
    instances = [
        make_instance("a1", "pdf", "Create PDF files"),
        make_instance("b2", "code-formatter", "Format code"),
    ]
    redundancy_candidates = build_redundancy_candidates(instances)
    assert _would_duplicate_redundant_family(instances[1], {"pdf"}, redundancy_candidates) is False


# --- _active_reasons ---

def test_active_reasons_scarce_category():
    reasons = _active_reasons(
        category_label="documents",
        repo_category_count=2,
        warning_count=0,
        heuristic_count=0,
        redundancy_penalty=0,
    )
    assert "category is relatively scarce" in reasons
    assert "no deterministic warnings" in reasons
    assert "no heuristic debt" in reasons
    assert "not currently in a redundant family" in reasons


def test_active_reasons_saturated():
    reasons = _active_reasons(
        category_label="documents",
        repo_category_count=15,
        warning_count=2,
        heuristic_count=1,
        redundancy_penalty=1,
    )
    assert "selected despite a saturated category" in reasons
    assert "category is relatively scarce" not in reasons
    assert "no deterministic warnings" not in reasons


# --- _active_score edge cases ---

def test_active_score_penalizes_warnings():
    clean = _active_score(repo_category_count=1, warning_count=0, heuristic_count=0, redundancy_penalty=0)
    warned = _active_score(repo_category_count=1, warning_count=3, heuristic_count=0, redundancy_penalty=0)
    assert warned < clean


def test_active_score_floors_at_zero():
    score = _active_score(repo_category_count=1, warning_count=50, heuristic_count=50, redundancy_penalty=50)
    assert score == 0
