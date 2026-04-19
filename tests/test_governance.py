from __future__ import annotations

from skill_auditor.analysis import (
    build_active_set,
    build_governance_actions,
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
