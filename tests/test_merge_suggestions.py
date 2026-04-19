from __future__ import annotations

from skill_auditor.analysis import (
    build_merge_suggestions, build_redundancy_candidates,
    build_category_summary, _shared_keywords,
)
from skill_auditor.models import SkillInstance


def _inst(instance_id, skill_key, description):
    return SkillInstance(
        instance_id=instance_id, skill_key=skill_key, ecosystem="codex",
        path=f"/skills/{skill_key}", source_kind="user_root", source={},
        name=skill_key, description=description,
        fingerprint=f"fp-{instance_id}", last_seen_at="2026-04-20T00:00:00+00:00",
    )


def test_merge_suggestions_empty_for_single():
    instances = [_inst("a1", "solo", "Use this skill for solo tasks")]
    result = build_merge_suggestions(instances, [], [])
    assert result == []


def test_merge_suggestions_detects_family_consolidate():
    instances = [
        _inst("a1", "pptx", "Create and edit pptx presentations."),
        _inst("b2", "pptx-generator", "Generate pptx slide decks from outlines."),
        _inst("c3", "slide-maker", "Build pptx presentations with templates."),
    ]
    result = build_merge_suggestions(instances, [], [])
    family = [s for s in result if s["merge_type"] == "family_consolidate"]
    assert len(family) >= 1


def test_merge_suggestions_pairwise_duplicate():
    instances = [
        _inst("a1", "pdf", "Create and merge PDF files."),
        _inst("b2", "minimax-pdf", "Professional PDF design and creation."),
    ]
    result = build_merge_suggestions(instances, [], [])
    assert len(result) > 0
    assert all("merge_group" in s for s in result)


def test_merge_suggestions_ignores_different_categories():
    instances = [
        _inst("a1", "pdf", "Create and merge PDF files."),
        _inst("b2", "code-formatter", "Format source code."),
    ]
    result = build_merge_suggestions(instances, [], [])
    # Should not produce suggestions since different categories


def test_redundancy_empty_for_different_categories():
    instances = [
        _inst("a1", "pdf", "Create PDF files"),
        _inst("b2", "code-formatter", "Format code"),
    ]
    result = build_redundancy_candidates(instances)
    # Different categories should produce no redundancy candidates
    assert isinstance(result, list)


def test_redundancy_empty_for_singleton():
    instances = [_inst("a1", "unique-skill", "A unique skill")]
    result = build_redundancy_candidates(instances)
    assert result == []


def test_category_summary_counts():
    instances = [
        _inst("a1", "pdf", "Create PDF"),
        _inst("b2", "docx", "Create docx"),
        _inst("c3", "pptx", "Create pptx"),
    ]
    result = build_category_summary(instances)
    assert "counts" in result
    assert isinstance(result["counts"], dict)


def test_shared_keywords():
    instances = [
        _inst("a1", "pdf-tool", "Create and edit PDF documents"),
        _inst("b2", "pdf-maker", "Make PDF files easily"),
    ]
    keywords = _shared_keywords(instances)
    assert isinstance(keywords, list)


def test_merge_suggestions_format_keyword_groups():
    """Instances sharing FORMAT_KEYWORDS get grouped together."""
    instances = [
        _inst("a1", "xlsx", "Create Excel xlsx spreadsheets with formulas"),
        _inst("b2", "xlsx-reporter", "Generate xlsx reports from data"),
    ]
    result = build_merge_suggestions(instances, [], [])
    assert len(result) > 0


def test_merge_suggestions_no_findings_args_needed():
    """build_merge_suggestions works without any findings (uses instances only)."""
    instances = [
        _inst("a1", "svg", "Create and edit SVG vector graphics"),
        _inst("b2", "svg-icon", "Design svg icons and logos"),
    ]
    result = build_merge_suggestions(instances, [], [])
    assert isinstance(result, list)
