from __future__ import annotations

import os
from pathlib import Path

from .errors import SkillAuditorError
from .models import ResolvedSkillTarget


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
                resolved_targets.append(
                    ResolvedSkillTarget(
                        path=str(skill_dir),
                        ecosystem=ecosystem,
                        source_kind=classify_source_kind(skill_dir, ecosystem, explicit=False),
                        source={"root": str(root)},
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
                resolved_targets.append(
                    ResolvedSkillTarget(
                        path=str(skill_dir),
                        ecosystem=ecosystem,
                        source_kind=classify_source_kind(skill_dir, ecosystem, explicit=True),
                        source={"requested_path": str(target_path)},
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
