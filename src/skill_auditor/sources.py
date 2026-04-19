from __future__ import annotations

import json
from pathlib import Path

from .discovery import (
    _detect_git_source,
    classify_source_kind,
    default_roots_for,
    discover_skill_dirs,
    resolve_ecosystems,
)
from .state import StateManager
from .utils import atomic_write_json, utc_now


def detect_git_source(path: Path) -> dict | None:
    return _detect_git_source(path)


def register_source(
    state: StateManager,
    instance_id: str,
    remote_url: str,
    ref: str | None = None,
) -> bool:
    ledger_path = state.state_root / "skill_ledger" / f"{instance_id}.json"
    if not ledger_path.exists():
        return False
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    source = ledger.get("source", {})
    source["url"] = remote_url
    if ref:
        source["ref"] = ref
    source["registered_at"] = utc_now()
    ledger["source"] = source
    ledger["source_kind"] = "git_clone"
    ledger["sync_protected"] = True
    atomic_write_json(ledger_path, ledger)
    return True


def list_sources(state: StateManager) -> list[dict]:
    ledger_dir = state.state_root / "skill_ledger"
    if not ledger_dir.exists():
        return []
    results = []
    for ledger_file in sorted(ledger_dir.iterdir()):
        if not ledger_file.name.endswith(".json"):
            continue
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        results.append({
            "instance_id": ledger.get("instance_id", ledger_file.stem),
            "skill_key": ledger.get("skill_key", ""),
            "source_kind": ledger.get("source_kind", "unknown"),
            "source": ledger.get("source", {}),
            "sync_protected": ledger.get("sync_protected", False),
            "tags": ledger.get("tags", []),
        })
    return results


def detect_all_sources(
    ecosystem: str | None = None,
) -> list[dict]:
    results = []
    ecosystems = resolve_ecosystems(ecosystem) if ecosystem else ["codex", "claude"]
    for eco in ecosystems:
        for root in default_roots_for(eco):
            for skill_dir in discover_skill_dirs(root):
                sk = classify_source_kind(skill_dir, eco, explicit=False)
                info = _detect_git_source(skill_dir) if sk in ("git_clone", "local_repo") else None
                results.append({
                    "path": str(skill_dir),
                    "ecosystem": eco,
                    "source_kind": sk,
                    "git_info": info,
                })
    return results
