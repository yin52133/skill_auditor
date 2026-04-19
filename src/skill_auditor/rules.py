from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import parse_skill_markdown
from .models import Finding, ParsedSkill, SkillInstance
from .utils import read_text_file


COMMON_ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}
CLAUDE_ALLOWED_KEYS = COMMON_ALLOWED_KEYS | {"compatibility"}

NAME_RE = re.compile(r"^[a-z0-9-]+$")
PIPE_TO_SHELL_RE = re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:bash|sh)\b")
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("security.secret.openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("security.secret.password_assignment", re.compile(r"(?i)\bpassword\s*[:=]\s*['\"]?[^\s'\"]+")),
    ("security.secret.private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def make_finding(
    instance: SkillInstance,
    *,
    rule_id: str,
    category: str,
    severity: str,
    path: Path,
    evidence: str,
    confidence: float = 1.0,
    suggested_fix: str | None = None,
    line_number: int | None = None,
    matched_text: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=confidence,
        ecosystem=instance.ecosystem,
        instance_id=instance.instance_id,
        path=str(path),
        evidence=evidence,
        suggested_fix=suggested_fix,
        line_number=line_number,
        matched_text=matched_text,
    )


def parse_instance_skill(instance: SkillInstance) -> ParsedSkill:
    return parse_skill_markdown(Path(instance.path) / "SKILL.md")


def validate_frontmatter(instance: SkillInstance, parsed_skill: ParsedSkill) -> list[Finding]:
    findings: list[Finding] = []
    skill_md = Path(instance.path) / "SKILL.md"

    for rule_id, message in parsed_skill.errors:
        findings.append(
            make_finding(
                instance,
                rule_id=rule_id,
                category="schema",
                severity="error",
                path=skill_md,
                evidence=message,
                suggested_fix="Add valid YAML frontmatter with name and description.",
            )
        )
    if parsed_skill.errors or parsed_skill.metadata is None:
        return findings

    metadata = parsed_skill.metadata
    allowed_keys = CLAUDE_ALLOWED_KEYS if instance.ecosystem == "claude" else COMMON_ALLOWED_KEYS
    unexpected = sorted(set(metadata) - allowed_keys)
    if unexpected:
        findings.append(
            make_finding(
                instance,
                rule_id="schema.frontmatter.unexpected_key",
                category="schema",
                severity="warn",
                path=skill_md,
                evidence=(
                    f"Unexpected frontmatter keys for {instance.ecosystem}: {', '.join(unexpected)}. "
                    f"Allowed keys: {', '.join(sorted(allowed_keys))}"
                ),
                suggested_fix="Treat extra frontmatter as ecosystem extension metadata unless it breaks parsing.",
            )
        )

    name = metadata.get("name")
    if name is None:
        findings.append(
            make_finding(
                instance,
                rule_id="schema.frontmatter.missing_name",
                category="schema",
                severity="error",
                path=skill_md,
                evidence="Frontmatter is missing required field 'name'.",
            )
        )
    elif not isinstance(name, str):
        findings.append(
            make_finding(
                instance,
                rule_id="schema.name.type",
                category="schema",
                severity="error",
                path=skill_md,
                evidence=f"Frontmatter field 'name' must be a string, got {type(name).__name__}.",
            )
        )
    else:
        stripped = name.strip()
        if not NAME_RE.match(stripped) or stripped.startswith("-") or stripped.endswith("-") or "--" in stripped:
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.name.format",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence=f"Skill name '{stripped}' must be kebab-case without edge or consecutive hyphens.",
                )
            )
        if len(stripped) > 64:
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.name.length",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence=f"Skill name length {len(stripped)} exceeds maximum 64.",
                )
            )

    description = metadata.get("description")
    if description is None:
        findings.append(
            make_finding(
                instance,
                rule_id="schema.frontmatter.missing_description",
                category="schema",
                severity="error",
                path=skill_md,
                evidence="Frontmatter is missing required field 'description'.",
            )
        )
    elif not isinstance(description, str):
        findings.append(
            make_finding(
                instance,
                rule_id="schema.description.type",
                category="schema",
                severity="error",
                path=skill_md,
                evidence=f"Frontmatter field 'description' must be a string, got {type(description).__name__}.",
            )
        )
    else:
        if "<" in description or ">" in description:
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.description.angle_brackets",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence="Description cannot contain angle brackets.",
                )
            )
        if len(description) > 1024:
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.description.length",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence=f"Description length {len(description)} exceeds maximum 1024.",
                )
            )

    compatibility = metadata.get("compatibility")
    if instance.ecosystem == "claude" and compatibility is not None:
        if not isinstance(compatibility, str):
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.compatibility.type",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence=f"Compatibility must be a string, got {type(compatibility).__name__}.",
                )
            )
        elif len(compatibility) > 500:
            findings.append(
                make_finding(
                    instance,
                    rule_id="schema.compatibility.length",
                    category="schema",
                    severity="error",
                    path=skill_md,
                    evidence=f"Compatibility length {len(compatibility)} exceeds maximum 500.",
                )
            )

    if instance.ecosystem == "codex" and metadata.get("license") is None:
        findings.append(
            make_finding(
                instance,
                rule_id="schema.frontmatter.missing_license",
                category="schema",
                severity="warn",
                path=skill_md,
                evidence="Codex skill is missing 'license' field. Anthropic official skills require license declaration.",
            )
        )

    line_count = parsed_skill.raw_content.count("\n") + 1
    if line_count > 500:
        findings.append(
            make_finding(
                instance,
                rule_id="structure.skill_md.too_long",
                category="structure",
                severity="warn",
                path=skill_md,
                evidence=f"SKILL.md is {line_count} lines; keep it below 500 lines when possible.",
            )
        )

    return findings


def validate_openai_yaml(instance: SkillInstance, parsed_skill: ParsedSkill) -> list[Finding]:
    if instance.ecosystem != "codex":
        return []

    findings: list[Finding] = []
    openai_yaml_path = Path(instance.path) / "agents" / "openai.yaml"
    if not openai_yaml_path.exists():
        return findings

    try:
        payload = yaml.safe_load(openai_yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [
            make_finding(
                instance,
                rule_id="codex.openai_yaml.invalid",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence=f"agents/openai.yaml failed to parse: {exc}",
                suggested_fix="If you rely on UI metadata, fix the YAML. Otherwise this is review-only metadata debt.",
            )
        ]

    interface = payload.get("interface")
    if not isinstance(interface, dict):
        return [
            make_finding(
                instance,
                rule_id="codex.openai_yaml.interface_missing",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence="agents/openai.yaml must contain an interface mapping.",
                suggested_fix="Add the interface block only if this skill needs Codex UI metadata.",
            )
        ]

    display_name = interface.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        findings.append(
            make_finding(
                instance,
                rule_id="codex.openai_yaml.display_name_missing",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence="interface.display_name must be a non-empty string.",
                suggested_fix="Add a display_name only if this skill needs polished UI metadata.",
            )
        )

    short_description = interface.get("short_description")
    if not isinstance(short_description, str) or not short_description.strip():
        findings.append(
            make_finding(
                instance,
                rule_id="codex.openai_yaml.short_description_missing",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence="interface.short_description must be a non-empty string.",
                suggested_fix="Add short_description only if this skill is meant to surface cleanly in the UI.",
            )
        )
    elif not 25 <= len(short_description) <= 64:
        findings.append(
            make_finding(
                instance,
                rule_id="codex.openai_yaml.short_description_length",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence=(
                    f"interface.short_description length {len(short_description)} is outside the allowed 25..64 range."
                ),
                suggested_fix="Shorten or expand the UI blurb if you care about Codex UI polish.",
            )
        )

    default_prompt = interface.get("default_prompt")
    skill_name = parsed_skill.metadata.get("name") if parsed_skill.metadata else instance.skill_key
    if default_prompt is not None and (not isinstance(default_prompt, str) or f"${skill_name}" not in default_prompt):
        findings.append(
            make_finding(
                instance,
                rule_id="codex.openai_yaml.default_prompt_missing_skill_ref",
                category="lifecycle",
                severity="warn",
                path=openai_yaml_path,
                evidence=f"interface.default_prompt must mention ${skill_name}.",
                suggested_fix="Only tune default_prompt if this skill depends on explicit UI invocation hints.",
            )
        )

    for field in ("icon_small", "icon_large"):
        value = interface.get(field)
        if isinstance(value, str):
            asset_path = (openai_yaml_path.parent / value).resolve()
            if not asset_path.exists():
                findings.append(
                    make_finding(
                        instance,
                        rule_id=f"codex.openai_yaml.{field}_missing",
                        category="lifecycle",
                        severity="warn",
                        path=openai_yaml_path,
                        evidence=f"{field} references missing asset {value}.",
                        suggested_fix="Provide the icon asset only if this skill needs polished Codex UI presentation.",
                    )
                )

    return findings


def scan_security_patterns(instance: SkillInstance) -> list[Finding]:
    findings: list[Finding] = []
    skill_dir = Path(instance.path)
    for file_path in sorted(path for path in skill_dir.rglob("*") if path.is_file()):
        text = read_text_file(file_path)
        if text is None:
            continue

        lines = text.splitlines()

        for line_idx, line in enumerate(lines, 1):
            m = PIPE_TO_SHELL_RE.search(line)
            if m:
                snippet = line.strip()[:120]
                findings.append(
                    make_finding(
                        instance,
                        rule_id="security.shell.pipe_to_shell",
                        category="smell",
                        severity="error",
                        path=file_path,
                        evidence=f"L{line_idx}: `{snippet}` — network output piped into shell interpreter.",
                        suggested_fix="Replace pipe-to-shell with a committed, reviewable script.",
                        line_number=line_idx,
                        matched_text=snippet,
                    )
                )

        opaque_hit = _find_opaque_binary_execution(lines)
        if opaque_hit:
            line_idx, snippet = opaque_hit
            findings.append(
                make_finding(
                    instance,
                    rule_id="security.binary.opaque_execution",
                    category="smell",
                    severity="error",
                    path=file_path,
                    evidence=f"L{line_idx}: `{snippet}` — direct execution of opaque temp/cache/download binary.",
                    line_number=line_idx,
                    matched_text=snippet,
                )
            )

        for rule_id, pattern in SECRET_PATTERNS:
            for line_idx, line in enumerate(lines, 1):
                match = pattern.search(line)
                if match:
                    if _should_skip_secret_match(file_path, rule_id, match.group(0)):
                        continue
                    snippet = match.group(0)[:120]
                    findings.append(
                        make_finding(
                            instance,
                            rule_id=rule_id,
                            category="smell",
                            severity="error",
                            path=file_path,
                            evidence=f"L{line_idx}: `{snippet}` — likely secret material.",
                            suggested_fix="Remove the secret and replace it with documented configuration input.",
                            line_number=line_idx,
                            matched_text=snippet,
                        )
                    )
                    break
    return findings


def validate_instance(instance: SkillInstance) -> list[Finding]:
    parsed_skill = parse_instance_skill(instance)
    findings = validate_frontmatter(instance, parsed_skill)
    findings.extend(validate_openai_yaml(instance, parsed_skill))
    findings.extend(scan_security_patterns(instance))
    return findings


def _find_opaque_binary_execution(lines: list[str]) -> tuple[int, str] | None:
    path_patterns = ("/tmp/", "/var/tmp/", "~/.cache/", ".cache/", "./Downloads/", "Downloads/")
    execution_verbs = ("bash ", "sh ", "zsh ", "fish ", "chmod +x ", "sudo ")
    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        if not any(pattern in stripped for pattern in path_patterns):
            continue
        if stripped.startswith(("/tmp/", "/var/tmp/")):
            if stripped.endswith("/"):
                continue
            return (line_idx, stripped[:120])
        if any(verb in stripped for verb in execution_verbs):
            return (line_idx, stripped[:120])
    return None


def _should_skip_secret_match(file_path: Path, rule_id: str, matched_text: str) -> bool:
    if rule_id != "security.secret.password_assignment":
        return False

    lowered = matched_text.lower()
    placeholder_markers = (
        "password123",
        "mypassword",
        "secret123",
        "z.string()",
        "_passwordcontroller",
        ".text",
    )
    is_doc_like = file_path.suffix.lower() in {".md", ".mdx", ".txt", ".rst"}
    return is_doc_like and any(marker in lowered for marker in placeholder_markers)
