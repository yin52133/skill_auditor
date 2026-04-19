from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from .models import UpgradeCandidate
from .state import StateManager
from .utils import compute_directory_fingerprint, utc_now


_BUILTIN_KINDS = frozenset({"builtin", "plugin_marketplace", "plugin_cache"})


def check_upgrades(
    *,
    instance_ids: list[str] | None = None,
    ecosystem: str | None = None,
) -> list[UpgradeCandidate]:
    state = StateManager()
    candidates: list[UpgradeCandidate] = []
    ledger_dir = state.state_root / "skill_ledger"

    if not ledger_dir.exists():
        return candidates

    for ledger_file in ledger_dir.iterdir():
        if not ledger_file.name.endswith(".json"):
            continue
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        instance_id = ledger.get("instance_id", ledger_file.stem)

        if instance_ids and instance_id not in instance_ids:
            continue

        source_kind = ledger.get("source_kind", "")
        if source_kind != "git_clone":
            continue

        source = ledger.get("source", {})
        remote_url = source.get("url")
        remote_ref = source.get("ref")
        current_commit = ledger.get("last_fingerprint", "")[:40]

        if not remote_url:
            continue

        remote_commit = _fetch_remote_commit(remote_url, remote_ref)
        changed_files = []
        diff_summary = ""

        if remote_commit and remote_commit != current_commit:
            changed_files, diff_summary = _get_remote_diff(remote_url, remote_ref, current_commit)

        candidates.append(
            UpgradeCandidate(
                instance_id=instance_id,
                skill_key=ledger.get("skill_key", ""),
                path=ledger.get("path", ""),
                current_ref=remote_ref,
                current_commit=current_commit,
                remote_url=remote_url,
                remote_ref=remote_ref,
                remote_commit=remote_commit,
                changed_files=changed_files,
                diff_summary=diff_summary,
            )
        )

    return candidates


def _fetch_remote_commit(remote_url: str, ref: str | None) -> str | None:
    try:
        result = subprocess.run(["git", "ls-remote", remote_url], capture_output=True, text=True, timeout=30)
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                commit, name = parts[0], parts[1]
                if ref and name == f"refs/heads/{ref}":
                    return commit
                if not ref and name.startswith("refs/heads/"):
                    return commit
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _get_remote_diff(remote_url: str, ref: str | None, base_commit: str) -> tuple[list[str], str]:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            clone_args = ["git", "clone", "--bare", "--depth=50"]
            if ref:
                clone_args.extend(["--branch", ref])
            clone_args.extend([remote_url, tmpdir])
            result = subprocess.run(clone_args, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return [], f"Clone failed: {result.stderr.strip()}"

            diff_result = subprocess.run(
                ["git", "-C", tmpdir, "diff", "--name-status", f"{base_commit}..HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            changed_files = [l for l in diff_result.stdout.strip().splitlines() if l]
            diff_lines = subprocess.run(
                ["git", "-C", tmpdir, "log", "--oneline", f"{base_commit}..HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            summary = diff_lines.stdout.strip()
            return changed_files, summary
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return [], "git unavailable"
    except Exception as e:
        return [], str(e)
    return [], ""


def apply_upgrade(
    candidate: UpgradeCandidate,
    *,
    dry_run: bool = False,
) -> tuple[bool, str | None, str | None]:
    if not candidate.remote_url:
        return False, None, "No remote URL"

    tmpdir: Path | None = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="skill-audit-upgrade-"))
        clone_args = ["git", "clone", "--depth=50"]
        if candidate.remote_ref:
            clone_args.extend(["--branch", candidate.remote_ref])
        clone_args.extend([candidate.remote_url, str(tmpdir)])

        result = subprocess.run(clone_args, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return False, None, f"Clone failed: {result.stderr.strip()}"

        skill_name = candidate.skill_key
        skill_dir = tmpdir
        for sub in tmpdir.iterdir():
            if sub.is_dir() and (sub / "SKILL.md").exists():
                skill_dir = sub
                break

        new_fingerprint = compute_directory_fingerprint(skill_dir)
        if dry_run:
            return True, new_fingerprint, None

        local_skill_dir = Path(candidate.path)
        if not local_skill_dir.exists():
            return False, None, f"Skill directory not found: {candidate.path}"

        for item in skill_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(skill_dir)
                dest = local_skill_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(item.read_bytes())

        _update_ledger_after_upgrade(candidate.instance_id, new_fingerprint)
        return True, new_fingerprint, None
    except Exception as e:
        return False, None, str(e)
    finally:
        if tmpdir and tmpdir.exists():
            import shutil
            shutil.rmtree(tmpdir)


def _update_ledger_after_upgrade(instance_id: str, new_fingerprint: str) -> None:
    state = StateManager()
    ledger_path = state.state_root / "skill_ledger" / f"{instance_id}.json"
    if not ledger_path.exists():
        return
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["last_fingerprint"] = new_fingerprint
    ledger["updated_at"] = utc_now()
    source = ledger.get("source", {})
    source["last_synced_at"] = utc_now()
    ledger["source"] = source

    from .utils import atomic_write_json
    atomic_write_json(ledger_path, ledger)
