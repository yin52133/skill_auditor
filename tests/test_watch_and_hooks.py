from __future__ import annotations

from pathlib import Path

from skill_auditor.cli import main
from skill_auditor.hooks import run_hook_check
from skill_auditor.watch import WatchSession


def invoke(argv: list[str], capsys) -> tuple[int, str, str]:
    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_watch_session_ignores_unowned_changes_and_skips_unchanged_fingerprint(tmp_path):
    from conftest import write_codex_skill, write_text

    root = tmp_path / "skills"
    skill_dir = write_codex_skill(root, "watched-skill")
    write_text(tmp_path / "README.md", "outside watch scope\n")

    session = WatchSession([root], ecosystem="codex")

    assert session.handle_changes([tmp_path / "README.md"]) == []

    first_actions = session.handle_changes([skill_dir / "SKILL.md"])
    second_actions = session.handle_changes([skill_dir / "SKILL.md"])

    assert len(first_actions) == 1
    assert first_actions[0].action == "audit"
    assert len(second_actions) == 1
    assert second_actions[0].action == "skip"


def test_hooks_install_writes_git_hook_scripts(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / ".git" / "hooks").mkdir(parents=True)

    exit_code, _stdout, _stderr = invoke(["hooks", "install", "--repo", str(repo)], capsys)

    pre_commit = repo / ".git" / "hooks" / "pre-commit"
    pre_push = repo / ".git" / "hooks" / "pre-push"

    assert exit_code == 0
    assert pre_commit.exists()
    assert pre_push.exists()
    assert "skill-auditor hook-run" in pre_commit.read_text(encoding="utf-8")
    assert pre_commit.stat().st_mode & 0o111


def test_hook_runner_blocks_only_deterministic_errors(tmp_path, monkeypatch):
    from conftest import write_codex_skill, write_text

    repo = tmp_path / "repo"
    skill_root = repo / "skills"
    skill_root.mkdir(parents=True)
    good_a = write_codex_skill(skill_root, "alpha-skill", description="Audit packages for trigger quality")
    write_codex_skill(skill_root, "beta-skill", description="Audit packages for trigger issues")
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path / "state"))

    allowed = run_hook_check(
        repo=repo,
        staged_files=[good_a / "SKILL.md", skill_root / "beta-skill" / "SKILL.md"],
        ecosystem="codex",
    )
    assert allowed.block is False

    bad_skill = skill_root / "bad-skill"
    write_text(bad_skill / "SKILL.md", "# broken\n")
    blocked = run_hook_check(
        repo=repo,
        staged_files=[bad_skill / "SKILL.md"],
        ecosystem="codex",
    )
    assert blocked.block is True
    assert blocked.error_count == 1
