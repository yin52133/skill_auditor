from __future__ import annotations

import json
from pathlib import Path

from .models import BatchEditResult
from .state import StateManager
from .utils import atomic_write_json


_BUILTIN_KINDS = frozenset({"builtin", "plugin_marketplace", "plugin_cache"})

_VALID_OPS = frozenset({
    "add_tag", "remove_tag", "set_note",
    "add_rule_exception", "remove_rule_exception", "set_sync_protected",
})


def batch_edit(
    state: StateManager,
    *,
    instance_ids: list[str] | None = None,
    selector: dict | None = None,
    operations: list[dict],
    include_protected: bool = False,
    include_builtin: bool = False,
    dry_run: bool = False,
) -> BatchEditResult:
    result = BatchEditResult(
        applied=[], skipped_protected=[], skipped_builtin=[], skipped_missing=[], failed=[],
    )

    ledger_dir = state.state_root / "skill_ledger"
    if not ledger_dir.exists():
        return result

    target_ids = _resolve_targets(ledger_dir, instance_ids=instance_ids, selector=selector)

    for iid in target_ids:
        ledger_path = ledger_dir / f"{iid}.json"
        if not ledger_path.exists():
            result.skipped_missing.append(iid)
            continue

        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        source_kind = ledger.get("source_kind", "unknown")

        if source_kind in _BUILTIN_KINDS and not include_builtin:
            result.skipped_builtin.append(iid)
            continue

        if ledger.get("sync_protected", False) and not include_protected:
            result.skipped_protected.append(iid)
            continue

        try:
            _apply_operations(ledger, operations)
            if not dry_run:
                atomic_write_json(ledger_path, ledger)
            result.applied.append(iid)
        except Exception as e:
            result.failed.append((iid, str(e)))

    return result


def _resolve_targets(
    ledger_dir: Path,
    *,
    instance_ids: list[str] | None,
    selector: dict | None,
) -> list[str]:
    if instance_ids:
        return instance_ids

    targets = []
    for ledger_file in sorted(ledger_dir.iterdir()):
        if not ledger_file.name.endswith(".json"):
            continue
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        if selector and not _matches_selector(ledger, selector):
            continue
        targets.append(ledger.get("instance_id", ledger_file.stem))
    return targets


def _matches_selector(ledger: dict, selector: dict) -> bool:
    for key, value in selector.items():
        if key == "ecosystem":
            iid = ledger.get("instance_id", "")
            if not iid.startswith(f"{value}:"):
                return False
        elif key == "source_kind":
            if ledger.get("source_kind") != value:
                return False
        elif key == "tag":
            if value not in ledger.get("tags", []):
                return False
        elif key == "path":
            source = ledger.get("source", {})
            if value not in (source.get("root", ""), source.get("requested_path", "")):
                return False
    return True


def _apply_operations(ledger: dict, operations: list[dict]) -> None:
    for op in operations:
        op_name = op.get("op", "")
        value = op.get("value")

        if op_name not in _VALID_OPS:
            raise ValueError(f"Unknown operation: {op_name}")

        if op_name == "add_tag":
            tags = ledger.setdefault("tags", [])
            if value not in tags:
                tags.append(value)
        elif op_name == "remove_tag":
            tags = ledger.get("tags", [])
            if value in tags:
                tags.remove(value)
        elif op_name == "set_note":
            ledger["note"] = value
        elif op_name == "add_rule_exception":
            excs = ledger.setdefault("rule_exceptions", [])
            if value not in excs:
                excs.append(value)
        elif op_name == "remove_rule_exception":
            excs = ledger.get("rule_exceptions", [])
            if value in excs:
                excs.remove(value)
        elif op_name == "set_sync_protected":
            ledger["sync_protected"] = bool(value)
