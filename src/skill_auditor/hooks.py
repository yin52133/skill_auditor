from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .discovery import find_owning_skill_dir, resolve_ecosystems
from .engine import run_audit
from .errors import SkillAuditorError
from .models import HookCheckResult


HOOK_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
exec skill-auditor hook-run --repo "$repo" --hook {hook_name}
"""


def install_hooks(repo: Path) -> None:
    git_dir = repo / ".git"
    hooks_dir = git_dir / "hooks"
    if not git_dir.exists() or not hooks_dir.exists():
        raise SkillAuditorError("REPO_NOT_FOUND", f"REPO_NOT_FOUND: {repo} is not a git repository.")
    for hook_name in ("pre-commit", "pre-push"):
        hook_path = hooks_dir / hook_name
        hook_path.write_text(HOOK_TEMPLATE.format(hook_name=hook_name), encoding="utf-8")
        hook_path.chmod(0o755)


def load_staged_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SkillAuditorError("ENGINE_BROKEN", f"ENGINE_BROKEN: failed to read staged files: {result.stderr.strip()}")
    return [repo / line for line in result.stdout.splitlines() if line.strip()]


def run_hook_check(*, repo: Path, staged_files: list[Path], ecosystem: str) -> HookCheckResult:
    impacted = []
    seen = set()
    for staged_path in staged_files:
        owning = find_owning_skill_dir(staged_path, stop_at=repo)
        if owning is None:
            continue
        resolved = str(owning.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        impacted.append(resolved)

    if not impacted:
        return HookCheckResult(block=False, error_count=0, impacted_skill_dirs=[], findings=[])

    report, _exit_code = run_audit(
        paths=impacted,
        use_all=False,
        ecosystem_request=ecosystem,
        output_format="text",
        active_set_max=30,
        audit_mode="git_hook",
        write_state=False,
        include_heuristics=False,
    )
    error_findings = [finding for finding in report.deterministic_findings if finding.severity == "error"]
    return HookCheckResult(
        block=bool(error_findings),
        error_count=len(error_findings),
        impacted_skill_dirs=impacted,
        findings=report.deterministic_findings,
    )


def run_hook_command(*, repo: Path, hook_name: str, ecosystem_request: str | None) -> int:
    ecosystems = resolve_ecosystems(ecosystem_request)
    ecosystem = ecosystems[0]
    result = run_hook_check(repo=repo, staged_files=load_staged_files(repo), ecosystem=ecosystem)
    if result.block:
        print(f"{hook_name}: blocked by {result.error_count} deterministic error finding(s).")
        for finding in result.findings:
            if finding.severity == "error":
                print(f"- {finding.rule_id}: {finding.evidence}")
        return 1
    print(f"{hook_name}: no deterministic blocking findings.")
    return 0
