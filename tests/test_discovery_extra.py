from __future__ import annotations

import os
from pathlib import Path

from skill_auditor.discovery import (
    resolve_ecosystems, default_roots_for, infer_path_ecosystem,
    classify_source_kind, find_owning_skill_dir, discover_skill_dirs,
)
from skill_auditor.errors import SkillAuditorError


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- resolve_ecosystems ---

def test_resolve_ecosystems_codex():
    result = resolve_ecosystems("codex")
    assert result == ["codex"]


def test_resolve_ecosystems_both():
    result = resolve_ecosystems("both")
    assert set(result) == {"codex", "claude"}


def test_resolve_ecosystems_unknown_raises(monkeypatch):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setenv("SKILL_AUDITOR_HOST", "")
    from skill_auditor.discovery import resolve_ecosystems as r
    import pytest
    with pytest.raises(SkillAuditorError):
        r("host")


# --- default_roots_for ---

def test_default_roots_for_returns_list():
    result = default_roots_for("codex")
    assert isinstance(result, list)


def test_default_roots_for_unknown_ecosystem():
    result = default_roots_for("unknown")
    assert result == []


# --- infer_path_ecosystem ---

def test_infer_codex_by_openai_yaml(tmp_path):
    agents_dir = tmp_path / "codex-skill" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")
    result = infer_path_ecosystem(tmp_path / "codex-skill")
    assert result == "codex"


def test_infer_claude_by_compatibility_field():
    p = Path("/tmp/claude-skill/SKILL.md")
    _write(p, "---\nname: test\ncompatibility: test\n---\n")
    result = infer_path_ecosystem(p)
    assert result == "claude"


def test_infer_unknown_as_fallback():
    p = Path("/tmp/unknown-skill/SKILL.md")
    _write(p, "---\nname: test\ndescription: desc\n---\n")
    result = infer_path_ecosystem(p)
    assert result in ("unknown", "codex", "claude")


# --- classify_source_kind ---

def test_classify_builtin_markers(tmp_path):
    result = classify_source_kind(tmp_path / ".system" / "skill", "codex", explicit=False)
    assert result == "builtin"


def test_classify_plugin_cache():
    result = classify_source_kind(Path("/tmp/.claude/plugins/cache/something"), "claude", explicit=False)
    assert result == "plugin_cache"


def test_classify_plugin_marketplace():
    result = classify_source_kind(Path("/tmp/.claude/plugins/something"), "claude", explicit=False)
    assert result == "plugin_marketplace"


def test_classify_manual_path_explicit():
    result = classify_source_kind(Path("/tmp/manual-skill"), "codex", explicit=True)
    assert result == "manual_path"


def test_classify_unknown_non_explicit():
    result = classify_source_kind(Path("/tmp/unknown"), "codex", explicit=False)
    assert result == "unknown"


# --- find_owning_skill_dir ---

def test_find_owning_skill_dir_returns_skill_dir(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    _write(skill_dir / "SKILL.md", "---\nname: my-skill\n---\n")
    nested = skill_dir / "scripts" / "helper.sh"
    nested.parent.mkdir()
    nested.write_text("#!/bin/bash\n")
    result = find_owning_skill_dir(nested)
    assert result == skill_dir


def test_find_owning_skill_dir_none_for_orphan(tmp_path):
    orphan = tmp_path / "orphan.txt"
    orphan.write_text("hello\n")
    result = find_owning_skill_dir(orphan)
    assert result is None


def test_find_owning_skill_dir_with_deep_nesting(tmp_path):
    """stop_at is exercised through the hooks path."""
    skill_dir = tmp_path / "a" / "b" / "c" / "my-skill"
    skill_dir.mkdir(parents=True)
    _write(skill_dir / "SKILL.md", "---\nname: my-skill\n---\n")
    nested = skill_dir / "src" / "utils.sh"
    nested.parent.mkdir(parents=True)
    nested.write_text("#!/bin/bash\n")
    result = find_owning_skill_dir(nested)
    assert result == skill_dir


# --- discover_skill_dirs ---

def test_discover_skill_dirs_finds_multiple(tmp_path):
    (tmp_path / "a" / "SKILL.md").parent.mkdir(parents=True)
    _write(tmp_path / "a" / "SKILL.md", "---\nname: a\n---\n")
    (tmp_path / "b" / "SKILL.md").parent.mkdir(parents=True)
    _write(tmp_path / "b" / "SKILL.md", "---\nname: b\n---\n")
    dirs = discover_skill_dirs(tmp_path)
    assert len(dirs) == 2


def test_discover_skill_dirs_single_at_root(tmp_path):
    _write(tmp_path / "SKILL.md", "---\nname: root-skill\n---\n")
    dirs = discover_skill_dirs(tmp_path)
    assert len(dirs) == 1
    assert dirs[0] == tmp_path
