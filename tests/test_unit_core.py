from __future__ import annotations

from pathlib import Path

from skill_auditor.frontmatter import parse_skill_markdown
from skill_auditor.utils import tokenize, make_instance_id, compute_directory_fingerprint, read_text_file
from skill_auditor.discovery import infer_path_ecosystem, classify_source_kind, find_owning_skill_dir, discover_skill_dirs


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- frontmatter ---

def test_parse_valid_frontmatter(tmp_path):
    write(tmp_path / "SKILL.md", "---\nname: foo\ndescription: bar\n---\n\n# Body\n")
    parsed = parse_skill_markdown(tmp_path / "SKILL.md")
    assert parsed.metadata == {"name": "foo", "description": "bar"}
    assert parsed.errors == []
    assert "# Body" in parsed.body


def test_parse_missing_frontmatter(tmp_path):
    write(tmp_path / "SKILL.md", "# No frontmatter\n")
    parsed = parse_skill_markdown(tmp_path / "SKILL.md")
    assert parsed.metadata is None
    assert any(r == "schema.frontmatter.missing" for r, _ in parsed.errors)


def test_parse_unclosed_frontmatter(tmp_path):
    write(tmp_path / "SKILL.md", "---\nname: broken\nbody text\n")
    parsed = parse_skill_markdown(tmp_path / "SKILL.md")
    assert parsed.metadata is None
    assert any(r == "schema.frontmatter.invalid" for r, _ in parsed.errors)


def test_parse_invalid_yaml_frontmatter(tmp_path):
    write(tmp_path / "SKILL.md", "---\n: invalid: yaml: [[\n---\n")
    parsed = parse_skill_markdown(tmp_path / "SKILL.md")
    assert parsed.metadata is None
    assert any(r == "schema.frontmatter.yaml_invalid" for r, _ in parsed.errors)


def test_parse_non_dict_frontmatter(tmp_path):
    write(tmp_path / "SKILL.md", "---\n- list\n- item\n---\n")
    parsed = parse_skill_markdown(tmp_path / "SKILL.md")
    assert parsed.metadata is None
    assert any(r == "schema.frontmatter.type" for r, _ in parsed.errors)


# --- tokenize ---

def test_tokenize_filters_stopwords():
    tokens = tokenize("the quick and the brown fox")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "quick" in tokens
    assert "brown" in tokens
    assert "fox" in tokens


def test_tokenize_empty_and_none():
    assert tokenize(None) == set()
    assert tokenize("") == set()


def test_tokenize_preserves_numbers():
    assert "123" in tokenize("value 123 test")


# --- make_instance_id ---

def test_make_instance_id_is_deterministic(tmp_path):
    a = make_instance_id("codex", tmp_path / "skills" / "foo")
    b = make_instance_id("codex", tmp_path / "skills" / "foo")
    assert a == b
    assert len(a) == 16


def test_make_instance_id_differs_by_ecosystem(tmp_path):
    a = make_instance_id("codex", tmp_path / "foo")
    b = make_instance_id("claude", tmp_path / "foo")
    assert a != b


# --- compute_directory_fingerprint ---

def test_fingerprint_changes_on_content_change(tmp_path):
    write(tmp_path / "SKILL.md", "v1")
    fp1 = compute_directory_fingerprint(tmp_path)
    write(tmp_path / "SKILL.md", "v2")
    fp2 = compute_directory_fingerprint(tmp_path)
    assert fp1 != fp2


# --- read_text_file ---

def test_read_text_file_returns_none_for_binary(tmp_path):
    p = tmp_path / "bin"
    p.write_bytes(b"\x00binary\x00data")
    assert read_text_file(p) is None


def test_read_text_file_returns_content(tmp_path):
    p = tmp_path / "text.txt"
    p.write_text("hello", encoding="utf-8")
    assert read_text_file(p) == "hello"


# --- discovery ---

def test_infer_codex_by_openai_yaml(tmp_path):
    write(tmp_path / "agents" / "openai.yaml", "interface: {}")
    assert infer_path_ecosystem(tmp_path) == "codex"


def test_infer_claude_by_compatibility(tmp_path):
    write(tmp_path / "SKILL.md", "---\nname: x\ndescription: y\ncompatibility: test\n---\n")
    assert infer_path_ecosystem(tmp_path) == "claude"


def test_find_owning_skill_dir_walks_up(tmp_path):
    write(tmp_path / "myskill" / "SKILL.md", "---\nname: x\n---\n")
    nested = tmp_path / "myskill" / "scripts" / "run.sh"
    write(nested, "#!/bin/bash")
    result = find_owning_skill_dir(nested)
    assert result == tmp_path / "myskill"


def test_find_owning_skill_dir_returns_none_for_orphan(tmp_path):
    write(tmp_path / "random.txt", "hello")
    assert find_owning_skill_dir(tmp_path / "random.txt") is None


def test_discover_skill_dirs_recursive(tmp_path):
    write(tmp_path / "a" / "SKILL.md", "---\nname: a\n---\n")
    write(tmp_path / "b" / "SKILL.md", "---\nname: b\n---\n")
    write(tmp_path / "c" / "not-a-skill.txt", "nope")
    dirs = discover_skill_dirs(tmp_path)
    assert len(dirs) == 2


def test_discover_skill_dirs_single_skill(tmp_path):
    write(tmp_path / "SKILL.md", "---\nname: single\n---\n")
    dirs = discover_skill_dirs(tmp_path)
    assert len(dirs) == 1
    assert dirs[0] == tmp_path
