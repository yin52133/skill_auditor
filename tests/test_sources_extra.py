from __future__ import annotations

import json
from pathlib import Path

from skill_auditor.sources import detect_git_source, register_source, list_sources, detect_all_sources
from skill_auditor.state import StateManager


def _init_git(path: Path) -> None:
    import subprocess
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)


def _setup_ledger(state_root: Path, instance_id: str, skill_key: str = "test-skill", **extra) -> None:
    ledger_dir = state_root / "skill_ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "instance_id": instance_id,
        "skill_key": skill_key,
        "source_kind": "user_root",
        "source": {},
        "tags": [],
        "rule_exceptions": [],
        "sync_protected": False,
        **extra,
    }
    (ledger_dir / f"{instance_id}.json").write_text(json.dumps(ledger), encoding="utf-8")


def test_detect_git_source_returns_none_for_non_git(tmp_path):
    result = detect_git_source(tmp_path / "not-a-repo")
    assert result is None


def test_detect_git_source_finds_git_repo(tmp_path):
    _init_git(tmp_path)
    import subprocess
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/test/repo.git"], cwd=tmp_path, capture_output=True)
    result = detect_git_source(tmp_path)
    assert result is not None
    assert "url" in result or "branch" in result or "is_detached" in result


def test_detect_git_source_returns_none_for_deep_file(tmp_path):
    _init_git(tmp_path)
    result = detect_git_source(tmp_path / "some" / "deep" / "file.txt")
    assert result is None


def test_register_source_updates_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "src1", "test-skill")
    state = StateManager()
    ok = register_source(state, "src1", "https://github.com/test/repo.git", ref="main")
    assert ok is True
    ledger = json.loads((tmp_path / "skill_ledger" / "src1.json").read_text())
    assert ledger["source"]["url"] == "https://github.com/test/repo.git"
    assert ledger["source"]["ref"] == "main"
    assert ledger["source_kind"] == "git_clone"
    assert ledger["sync_protected"] is True


def test_register_source_sets_registered_at(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "src2", "test-skill")
    state = StateManager()
    register_source(state, "src2", "https://github.com/test/repo.git")
    ledger = json.loads((tmp_path / "skill_ledger" / "src2.json").read_text())
    assert "registered_at" in ledger["source"]


def test_register_source_returns_false_for_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    ok = register_source(state, "nonexistent", "https://x.git", None)
    assert ok is False
