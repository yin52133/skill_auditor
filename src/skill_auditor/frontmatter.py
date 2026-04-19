from __future__ import annotations

import re
from pathlib import Path

import yaml

from .models import ParsedSkill


FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


def parse_skill_markdown(skill_md: Path) -> ParsedSkill:
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return ParsedSkill(
            metadata=None,
            body=content,
            errors=[("schema.frontmatter.missing", "SKILL.md must start with YAML frontmatter")],
            raw_content=content,
        )

    match = FRONTMATTER_RE.match(content)
    if not match:
        return ParsedSkill(
            metadata=None,
            body=content,
            errors=[("schema.frontmatter.invalid", "Frontmatter must have a closing --- delimiter")],
            raw_content=content,
        )

    frontmatter_text, body = match.groups()
    try:
        metadata = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        return ParsedSkill(
            metadata=None,
            body=body,
            errors=[("schema.frontmatter.yaml_invalid", f"Invalid YAML in frontmatter: {exc}")],
            raw_content=content,
        )

    if not isinstance(metadata, dict):
        return ParsedSkill(
            metadata=None,
            body=body,
            errors=[("schema.frontmatter.type", "Frontmatter must parse to a YAML mapping")],
            raw_content=content,
        )

    return ParsedSkill(metadata=metadata, body=body, errors=[], raw_content=content)
