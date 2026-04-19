from __future__ import annotations

import json
from pathlib import Path

from skill_auditor.sources import list_sources, register_source, detect_all_sources
from skill_auditor.state import StateManager


def _setup_ledger(state_root: Path, instance_id: str, skill_key: str, **extra) -> None:
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


def test_list_sources_returns_empty_when_no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    assert list_sources(state) == []


def test_list_sources_returns_registered_sources(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", "my-skill", tags=["reviewed"], source_kind="git_clone")
    state = StateManager()
    sources = list_sources(state)
    assert len(sources) == 1
    assert sources[0]["skill_key"] == "my-skill"
    assert sources[0]["source_kind"] == "git_clone"
    assert sources[0]["tags"] == ["reviewed"]


def test_list_sources_skips_non_json_files(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", "foo")
    (tmp_path / "skill_ledger" / "readme.txt").write_text("not a ledger", encoding="utf-8")
    state = StateManager()
    sources = list_sources(state)
    assert len(sources) == 1


def test_register_source_updates_git_url(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", "foo")
    state = StateManager()
    result = register_source(state, "a1", "https://example.com/foo.git", "v1.0")
    assert result is True
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert ledger["source"]["url"] == "https://example.com/foo.git"
    assert ledger["source"]["ref"] == "v1.0"
    assert ledger["sync_protected"] is True


def test_register_source_returns_false_for_missing_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    result = register_source(state, "nonexistent", "https://x.git", None)
    assert result is False
