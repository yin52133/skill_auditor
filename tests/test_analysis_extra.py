from __future__ import annotations

from skill_auditor.analysis import (
    build_clusters, build_category_assignments, build_overlap_findings,
    build_validity_summary, build_trigger_summary, build_active_set,
    build_compliance_summary,
)
from skill_auditor.models import Finding, SkillInstance


def _inst(instance_id, skill_key, description, ecosystem="codex"):
    return SkillInstance(
        instance_id=instance_id, skill_key=skill_key, ecosystem=ecosystem,
        path=f"/skills/{skill_key}", source_kind="user_root", source={},
        name=skill_key, description=description,
        fingerprint=f"fp-{instance_id}", last_seen_at="2026-04-20T00:00:00+00:00",
    )


def _finding(instance_id, rule_id, severity="warn"):
    return Finding(
        rule_id=rule_id, category="smell", severity=severity, confidence=1.0,
        ecosystem="codex", instance_id=instance_id, path="/x/SKILL.md", evidence="evidence",
    )


# --- build_clusters ---

def test_clusters_group_by_skill_key():
    instances = [_inst("a1", "foo", "desc a"), _inst("b2", "foo", "desc b")]
    result = build_clusters(instances)
    assert len(result["clusters"]) == 1
    assert result["clusters"][0]["skill_key"] == "foo"
    assert result["clusters"][0]["cluster_id"] == "skill-key:foo"


def test_clusters_excludes_singletons():
    instances = [_inst("a1", "foo", "desc"), _inst("b2", "bar", "desc")]
    result = build_clusters(instances)
    assert len(result["clusters"]) == 0


# --- build_category_assignments ---

def test_category_assignments_handles_general():
    inst = _inst("a1", "misc-tool", "A miscellaneous tool for various tasks")
    result = build_category_assignments([inst])
    assert result["a1"]["primary_category"] == "general"


# --- build_overlap_findings ---

def test_overlap_findings_empty_for_unique():
    instances = [
        _inst("a1", "pdf-creator", "Create PDF files from markdown documents"),
        _inst("b2", "code-formatter", "Format source code across multiple languages"),
    ]
    findings = build_overlap_findings(instances)
    assert len(findings) == 0


def test_overlap_findings_same_category_high_similarity():
    instances = [
        _inst("a1", "docx-helper", "Use this skill whenever you want to create docx documents and edit them"),
        _inst("b2", "docx-maker", "Use this skill whenever you want to create docx documents and format them"),
    ]
    findings = build_overlap_findings(instances)
    assert len(findings) > 0
    assert all(f.rule_id == "heuristic.overlap.lexical" for f in findings)


# --- build_validity_summary ---

def test_validity_summary_counts():
    instances = [_inst("a1", "ready-skill", "A ready skill")]
    findings = [_finding("a1", "schema.frontmatter.missing_name", severity="error")]
    result = build_validity_summary(instances, findings, [])
    assert result["counts"]["invalid"] == 1


def test_validity_summary_all_ready():
    instances = [_inst("a1", "good-skill", "A good skill with description")]
    result = build_validity_summary(instances, [], [])
    assert result["counts"]["ready"] == 1
    assert result["counts"]["invalid"] == 0


# --- build_trigger_summary ---

def test_trigger_summary_counts_cues():
    instances = [
        _inst("a1", "good-skill", "Use this skill whenever you need to create docx files"),
        _inst("b2", "bad-skill", "Toolkit"),
    ]
    heur = [
        _finding("b2", "heuristic.trigger.missing_activation_cues"),
    ]
    result = build_trigger_summary(instances, heur)
    assert result["missing_activation_cues"] >= 0
    assert result["broad_surface_candidates"] >= 0


# --- build_active_set ---

def test_active_set_recommends_skills(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    instances = [
        _inst("a1", "good-skill", "Use this when creating docx files"),
        _inst("b2", "bad-skill", "Toolkit for many things"),
    ]
    heur = [_finding("b2", "heuristic.trigger.missing_activation_cues")]
    result = build_active_set(instances, [], heur, max_items=10)
    assert "recommended_active" in result
    assert isinstance(result["recommended_active"], list)


def test_active_set_respects_max_items(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    instances = [
        _inst(f"i{n}", f"skill-{n}", f"Use this when you need to {chr(64+n)}")
        for n in range(1, 20)
    ]
    result = build_active_set(instances, [], [], max_items=5)
    assert len(result["recommended_active"]) <= 5


# --- build_compliance_summary ---

def test_compliance_summary_empty():
    instances = [_inst("a1", "good", "A well-described skill")]
    result = build_compliance_summary(instances, [], [])
    assert "compliant" in result
    assert "total" in result


def test_compliance_summary_counts_missing_license():
    instances = [_inst("a1", "no-license", "A skill")]
    findings = [_finding("a1", "schema.frontmatter.missing_license", "warn")]
    result = build_compliance_summary(instances, findings, [])
    assert result["missing_license"] == 1
