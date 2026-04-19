from __future__ import annotations

import json
from pathlib import Path

from skill_auditor.batch import batch_edit
from skill_auditor.state import StateManager


def _setup_ledger(state_root: Path, instance_id: str, **extra) -> Path:
    ledger_dir = state_root / "skill_ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "instance_id": instance_id,
        "skill_key": f"skill-{instance_id}",
        "source_kind": "user_root",
        "source": {},
        "tags": [],
        "rule_exceptions": [],
        "sync_protected": False,
        **extra,
    }
    path = ledger_dir / f"{instance_id}.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    return path


def test_batch_add_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1")
    state = StateManager()
    result = batch_edit(state, instance_ids=["a1"], operations=[{"op": "add_tag", "value": "reviewed"}])
    assert "a1" in result.applied
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert "reviewed" in ledger["tags"]


def test_batch_remove_tag(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", tags=["old"])
    state = StateManager()
    batch_edit(state, instance_ids=["a1"], operations=[{"op": "remove_tag", "value": "old"}])
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert "old" not in ledger["tags"]


def test_batch_set_note(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1")
    state = StateManager()
    batch_edit(state, instance_ids=["a1"], operations=[{"op": "set_note", "value": "keep this"}])
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert ledger["note"] == "keep this"


def test_batch_add_rule_exception(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1")
    state = StateManager()
    batch_edit(state, instance_ids=["a1"], operations=[{"op": "add_rule_exception", "value": "security.shell.pipe_to_shell"}])
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert "security.shell.pipe_to_shell" in ledger["rule_exceptions"]


def test_batch_skips_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", sync_protected=True)
    state = StateManager()
    result = batch_edit(state, instance_ids=["a1"], operations=[{"op": "set_note", "value": "x"}])
    assert "a1" in result.skipped_protected
    assert result.applied == []


def test_batch_skips_builtin(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1", source_kind="plugin_cache")
    state = StateManager()
    result = batch_edit(state, instance_ids=["a1"], operations=[{"op": "set_note", "value": "x"}])
    assert "a1" in result.skipped_builtin


def test_batch_skips_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    (tmp_path / "skill_ledger").mkdir(parents=True, exist_ok=True)
    state = StateManager()
    result = batch_edit(state, instance_ids=["nonexistent"], operations=[{"op": "set_note", "value": "x"}])
    assert "nonexistent" in result.skipped_missing


def test_batch_dry_run_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1")
    state = StateManager()
    result = batch_edit(state, instance_ids=["a1"], operations=[{"op": "set_note", "value": "nope"}], dry_run=True)
    assert "a1" in result.applied
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert "note" not in ledger


def test_batch_selector_by_ecosystem(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "codex:abc", source_kind="user_root")
    _setup_ledger(tmp_path, "claude:xyz", source_kind="user_root")
    state = StateManager()
    result = batch_edit(state, selector={"ecosystem": "codex"}, operations=[{"op": "add_tag", "value": "tagged"}])
    assert "codex:abc" in result.applied
    assert "claude:xyz" not in result.applied


def test_batch_set_sync_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "a1")
    state = StateManager()
    batch_edit(state, instance_ids=["a1"], operations=[{"op": "set_sync_protected", "value": True}])
    ledger = json.loads((tmp_path / "skill_ledger" / "a1.json").read_text())
    assert ledger["sync_protected"] is True
