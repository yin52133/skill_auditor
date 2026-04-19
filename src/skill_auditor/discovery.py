from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

from .errors import SkillAuditorError
from .models import ResolvedSkillTarget


_BUILTIN_MARKERS = {"/.system/", "/.builtin/"}


def _detect_git_source(path: Path) -> dict[str, str | bool] | None:
    current = path if path.is_dir() else path.parent
    while True:
        git_dir = current / ".git"
        if git_dir.exists():
            break
        if current.parent == current:
            return None
        current = current.parent

    config_path = git_dir / "config" if git_dir.is_dir() else None
    url: str | None = None
    ref: str | None = None

    if config_path and config_path.exists():
        cp = configparser.ConfigParser()
        try:
            cp.read(str(config_path), encoding="utf-8")
        except configparser.Error:
            pass
        else:
            if cp.has_option('remote "origin"', "url"):
                url = cp.get('remote "origin"', "url")

    if url is None:
        try:
            result = subprocess.run(
                ["git", "-C", str(current), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    if url is None:
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(current), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            ref = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    commit: str | None = None
    try:
        result = subprocess.run(
            ["git", "-C", str(current), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    is_remote = url.startswith("https://") or url.startswith("http://") or url.startswith("git@") or url.startswith("ssh://")
    return {"url": url, "ref": ref, "commit": commit, "is_remote": is_remote}


def detect_host_ecosystem() -> str | None:
    explicit = os.environ.get("SKILL_AUDITOR_HOST")
    if explicit in {"codex", "claude"}:
        return explicit
    if os.environ.get("CODEX_HOME"):
        return "codex"
    if os.environ.get("CLAUDE_HOME"):
        return "claude"
    return None


def resolve_ecosystems(requested: str | None) -> list[str]:
    if requested in {None, "host"}:
        host = detect_host_ecosystem()
        if host is None:
            raise SkillAuditorError(
                "HOST_ECOSYSTEM_UNKNOWN",
                "HOST_ECOSYSTEM_UNKNOWN: unable to detect the current host ecosystem. "
                "Pass --ecosystem codex, --ecosystem claude, or --ecosystem both.",
            )
        return [host]
    if requested == "both":
        return ["codex", "claude"]
    return [requested]


def default_roots_for(ecosystem: str) -> list[Path]:
    if ecosystem == "codex":
        home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        candidates = [home / "skills", home / "plugins" / "cache"]
    elif ecosystem == "claude":
        home = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")).expanduser()
        candidates = [home / "skills", home / "plugins"]
    else:
        candidates = []
    return [candidate for candidate in candidates if candidate.exists()]


def infer_path_ecosystem(path: Path) -> str:
    skill_dir = path if path.is_dir() else path.parent
    if (skill_dir / "agents" / "openai.yaml").exists():
        return "codex"
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        if "compatibility:" in text:
            return "claude"
    host = detect_host_ecosystem()
    if host:
        return host
    return "unknown"


def classify_source_kind(path: Path, ecosystem: str, *, explicit: bool) -> str:
    path_str = path.as_posix()

    if any(marker in path_str for marker in _BUILTIN_MARKERS):
        return "builtin"

    source_info = _detect_git_source(path)
    if source_info is not None:
        return "git_clone" if source_info["is_remote"] else "local_repo"

    if "/plugins/cache/" in path_str:
        return "plugin_cache"
    if "/plugins/" in path_str and ecosystem == "claude":
        return "plugin_marketplace"
    for root in default_roots_for(ecosystem):
        if path.is_relative_to(root):
            return "user_root"
    return "manual_path" if explicit else "unknown"


def find_owning_skill_dir(path: Path, *, stop_at: Path | None = None) -> Path | None:
    current = path if path.is_dir() else path.parent
    stop_at = stop_at.resolve() if stop_at else None
    while True:
        if (current / "SKILL.md").exists():
            return current
        if stop_at and current == stop_at:
            return None
        if current.parent == current:
            return None
        current = current.parent


def discover_skill_dirs(root: Path) -> list[Path]:
    if root.is_file():
        owning = find_owning_skill_dir(root)
        return [owning] if owning else []
    if (root / "SKILL.md").exists():
        return [root]
    return sorted({skill_md.parent.resolve() for skill_md in root.rglob("SKILL.md")})


def resolve_targets(paths: list[str], *, use_all: bool, ecosystem_request: str | None) -> list[ResolvedSkillTarget]:
    if use_all and paths:
        raise SkillAuditorError("INVALID_ARGUMENT", "INVALID_ARGUMENT: pass paths or --all, not both.")

    resolved_targets: list[ResolvedSkillTarget] = []
    if use_all:
        ecosystems = resolve_ecosystems(ecosystem_request)
        candidate_roots: list[tuple[Path, str]] = []
        for ecosystem in ecosystems:
            for root in default_roots_for(ecosystem):
                candidate_roots.append((root, ecosystem))
        if not candidate_roots:
            raise SkillAuditorError("TARGET_NOT_FOUND", "TARGET_NOT_FOUND: no installed skill roots found.")
        for root, ecosystem in candidate_roots:
            for skill_dir in discover_skill_dirs(root):
                sk = classify_source_kind(skill_dir, ecosystem, explicit=False)
                src: dict[str, str] = {"root": str(root)}
                if sk in ("git_clone", "local_repo"):
                    info = _detect_git_source(skill_dir)
                    if info:
                        src.update({k: str(v) for k, v in info.items()})
                resolved_targets.append(
                    ResolvedSkillTarget(
                        path=str(skill_dir),
                        ecosystem=ecosystem,
                        source_kind=sk,
                        source=src,
                    )
                )
    else:
        if not paths:
            raise SkillAuditorError("INVALID_ARGUMENT", "INVALID_ARGUMENT: provide one or more paths or use --all.")
        ecosystems = None if ecosystem_request in {None, "host"} else resolve_ecosystems(ecosystem_request)
        for raw_path in paths:
            target_path = Path(raw_path).expanduser().resolve()
            if not target_path.exists():
                continue
            skill_dirs = discover_skill_dirs(target_path)
            for skill_dir in skill_dirs:
                ecosystem = ecosystems[0] if ecosystems else infer_path_ecosystem(skill_dir)
                sk = classify_source_kind(skill_dir, ecosystem, explicit=True)
                src: dict[str, str] = {"requested_path": str(target_path)}
                if sk in ("git_clone", "local_repo"):
                    info = _detect_git_source(skill_dir)
                    if info:
                        src.update({k: str(v) for k, v in info.items()})
                resolved_targets.append(
                    ResolvedSkillTarget(
                        path=str(skill_dir),
                        ecosystem=ecosystem,
                        source_kind=sk,
                        source=src,
                    )
                )

    deduped: list[ResolvedSkillTarget] = []
    seen = set()
    for target in resolved_targets:
        key = (target.path, target.ecosystem)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)

    if not deduped:
        raise SkillAuditorError("TARGET_NOT_FOUND", "TARGET_NOT_FOUND: no matching skill instance found.")
    return sorted(deduped, key=lambda item: (item.ecosystem, item.path))
