from __future__ import annotations

import signal
import time
from pathlib import Path

from .discovery import find_owning_skill_dir, resolve_targets
from .engine import run_audit
from .models import WatchAction
from .utils import compute_directory_fingerprint


class WatchSession:
    def __init__(self, roots: list[Path], *, ecosystem: str):
        self.roots = [root.resolve() for root in roots]
        self.ecosystem = ecosystem
        self.last_fingerprints: dict[str, str] = {}

    def handle_changes(self, changed_paths: list[Path]) -> list[WatchAction]:
        actions: list[WatchAction] = []
        seen = set()
        for changed_path in changed_paths:
            resolved = changed_path.resolve()
            if not any(resolved.is_relative_to(root) for root in self.roots):
                continue
            owning = find_owning_skill_dir(resolved)
            if owning is None:
                continue
            owning_key = str(owning.resolve())
            if owning_key in seen:
                continue
            seen.add(owning_key)
            fingerprint = compute_directory_fingerprint(owning)
            previous = self.last_fingerprints.get(owning_key)
            if previous == fingerprint:
                actions.append(WatchAction(action="skip", skill_dir=owning_key, reason="unchanged fingerprint"))
                continue
            self.last_fingerprints[owning_key] = fingerprint
            actions.append(WatchAction(action="audit", skill_dir=owning_key, reason="owned file changed"))
        return actions


def run_watch_loop(*, paths: list[str], ecosystem_request: str | None, output_format: str) -> int:
    targets = resolve_targets(paths, use_all=not paths, ecosystem_request=ecosystem_request)
    roots = sorted({Path(target.path) for target in targets})
    ecosystem = targets[0].ecosystem if targets else "unknown"
    session = WatchSession(roots, ecosystem=ecosystem)
    stop = {"requested": False}

    def _request_stop(_signum, _frame):
        stop["requested"] = True

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    mtimes: dict[str, float] = {}
    while not stop["requested"]:
        changed_paths: list[Path] = []
        for root in roots:
            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue
                key = str(file_path.resolve())
                mtime = file_path.stat().st_mtime
                if mtimes.get(key) != mtime:
                    if key in mtimes:
                        changed_paths.append(file_path)
                    mtimes[key] = mtime
        for action in session.handle_changes(changed_paths):
            if action.action != "audit":
                continue
            run_audit(
                paths=[action.skill_dir],
                use_all=False,
                ecosystem_request=ecosystem,
                output_format=output_format,
                active_set_max=30,
                audit_mode="watch",
                write_state=True,
                include_heuristics=True,
            )
        time.sleep(0.25)
    return 0
