from __future__ import annotations

from pathlib import Path


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_codex_skill(
    root: Path,
    name: str,
    description: str = "Audit Codex skills deterministically.",
    *,
    with_openai_yaml: bool = True,
    extra_frontmatter: str = "",
    extra_files: dict[str, str] | None = None,
) -> Path:
    skill_dir = root / name
    frontmatter = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if extra_frontmatter:
        frontmatter.append(extra_frontmatter.rstrip("\n"))
    frontmatter.extend(["---", "", f"# {name}"])
    write_text(skill_dir / "SKILL.md", "\n".join(frontmatter) + "\n")

    if with_openai_yaml:
        write_text(
            skill_dir / "agents" / "openai.yaml",
            "\n".join(
                [
                    "interface:",
                    f'  display_name: "{name.title()}"',
                    '  short_description: "Audit and maintain skill packages"',
                    f'  default_prompt: "Use ${name} to audit this skill package."',
                ]
            )
            + "\n",
        )

    for relative_path, content in (extra_files or {}).items():
        write_text(skill_dir / relative_path, content)

    return skill_dir


def write_claude_skill(
    root: Path,
    name: str,
    description: str = "Audit Claude skills safely.",
    *,
    compatibility: str = "Requires Python 3.11",
    extra_files: dict[str, str] | None = None,
) -> Path:
    skill_dir = root / name
    write_text(
        skill_dir / "SKILL.md",
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                f"compatibility: {compatibility}",
                "---",
                "",
                f"# {name}",
            ]
        )
        + "\n",
    )

    for relative_path, content in (extra_files or {}).items():
        write_text(skill_dir / relative_path, content)

    return skill_dir
