from __future__ import annotations

from pathlib import Path

from skill_auditor.watch import WatchSession


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_watch_session_detects_changed_skill(tmp_path):
    _write(tmp_path / "skills" / "my-skill" / "SKILL.md", "---\nname: my-skill\n---\n")
    session = WatchSession([tmp_path / "skills"], ecosystem="codex")

    actions = session.handle_changes([tmp_path / "skills" / "my-skill" / "SKILL.md"])
    assert len(actions) == 1
    assert actions[0].action == "audit"


def test_watch_session_skips_unchanged_fingerprint(tmp_path):
    _write(tmp_path / "skills" / "my-skill" / "SKILL.md", "---\nname: my-skill\n---\n")
    session = WatchSession([tmp_path / "skills"], ecosystem="codex")

    session.handle_changes([tmp_path / "skills" / "my-skill" / "SKILL.md"])
    actions = session.handle_changes([tmp_path / "skills" / "my-skill" / "SKILL.md"])
    assert len(actions) == 1
    assert actions[0].action == "skip"


def test_watch_session_ignores_files_outside_roots(tmp_path):
    _write(tmp_path / "other" / "SKILL.md", "---\nname: x\n---\n")
    session = WatchSession([tmp_path / "skills"], ecosystem="codex")

    actions = session.handle_changes([tmp_path / "other" / "SKILL.md"])
    assert len(actions) == 0


def test_watch_session_deduplicates_same_skill(tmp_path):
    skill_dir = tmp_path / "skills" / "my-skill"
    _write(skill_dir / "SKILL.md", "---\nname: my-skill\n---\n")
    _write(skill_dir / "run.sh", "#!/bin/bash\necho hello")
    session = WatchSession([tmp_path / "skills"], ecosystem="codex")

    actions = session.handle_changes([skill_dir / "SKILL.md", skill_dir / "run.sh"])
    assert len(actions) == 1


def test_watch_session_detects_change_after_modify(tmp_path):
    _write(tmp_path / "skills" / "my-skill" / "SKILL.md", "---\nname: my-skill\n---\nv1\n")
    session = WatchSession([tmp_path / "skills"], ecosystem="codex")

    session.handle_changes([tmp_path / "skills" / "my-skill" / "SKILL.md"])
    _write(tmp_path / "skills" / "my-skill" / "SKILL.md", "---\nname: my-skill\n---\nv2\n")
    actions = session.handle_changes([tmp_path / "skills" / "my-skill" / "SKILL.md"])
    assert len(actions) == 1
    assert actions[0].action == "audit"
