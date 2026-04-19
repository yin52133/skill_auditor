from __future__ import annotations

import json
from pathlib import Path

from skill_auditor.cli import main
from skill_auditor.state import StateManager


def _setup_ledger(state_root: Path, instance_id: str, **extra) -> None:
    ledger_dir = state_root / "skill_ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = {
        "instance_id": instance_id,
        "skill_key": f"skill-{instance_id}",
        "source_kind": "git_clone",
        "source": {"url": "https://github.com/test/repo.git", "ref": "main"},
        "tags": [],
        "rule_exceptions": [],
        "sync_protected": False,
        "last_fingerprint": "a" * 40,
        **extra,
    }
    (ledger_dir / f"{instance_id}.json").write_text(json.dumps(ledger), encoding="utf-8")


def test_source_list_json_format(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "s1", skill_key="my-skill")
    code = main(["source", "list", "--format", "json"])
    assert code == 0


def test_source_list_text_format(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "s2", skill_key="another-skill")
    code = main(["source", "list"])
    assert code == 0


def test_source_register_not_found(tmp_path, monkeypatch):
    """register returns non-zero when instance_id is not in ledger."""
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    state = StateManager()
    state.state_root.mkdir(parents=True, exist_ok=True)
    code = main(["source", "register", "--path", "/skills/test-skill", "--repo", "https://example.com/repo.git"])
    assert code == 1


def test_batch_tag_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "b1")
    code = main(["batch", "tag", "--add", "reviewed", "--dry-run"])
    assert code == 0


def test_batch_tag_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "b2")
    code = main(["batch", "tag", "--add", "staged"])
    assert code == 0
    ledger = json.loads((tmp_path / "skill_ledger" / "b2.json").read_text())
    assert "staged" in ledger["tags"]


def test_batch_note_set(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "b3")
    code = main(["batch", "note", "--set", "important skill"])
    assert code == 0
    ledger = json.loads((tmp_path / "skill_ledger" / "b3.json").read_text())
    assert ledger["note"] == "important skill"


def test_batch_protect_on(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    _setup_ledger(tmp_path, "b4")
    code = main(["batch", "protect", "--on"])
    assert code == 0
    ledger = json.loads((tmp_path / "skill_ledger" / "b4.json").read_text())
    assert ledger["sync_protected"] is True


def test_upgrade_check_no_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    code = main(["upgrade", "check"])
    assert code == 0


def test_upgrade_check_json_format(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    code = main(["upgrade", "check", "--format", "json"])
    assert code == 0
