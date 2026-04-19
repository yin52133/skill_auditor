from __future__ import annotations

import pytest

from skill_auditor.cli import build_parser, main


def test_parser_audit_defaults():
    parser = build_parser()
    args = parser.parse_args(["audit"])
    assert args.command == "audit"
    assert args.format == "text"
    assert args.language == "en"
    assert args.ecosystem == "host"
    assert args.active_set_max == 30
    assert args.all is False


def test_parser_audit_with_options():
    parser = build_parser()
    args = parser.parse_args(["audit", "--format", "json", "--language", "zh", "--ecosystem", "claude", "--active-set-max", "5", "--all", "/some/path"])
    assert args.format == "json"
    assert args.language == "zh"
    assert args.ecosystem == "claude"
    assert args.active_set_max == 5
    assert args.all is True
    assert args.paths == ["/some/path"]


def test_parser_requires_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_hooks_install_claude():
    parser = build_parser()
    args = parser.parse_args(["hooks", "install-claude", "--scope", "project"])
    assert args.hooks_command == "install-claude"
    assert args.scope == "project"


def test_parser_batch_tag():
    parser = build_parser()
    args = parser.parse_args(["batch", "tag", "--add", "reviewed", "--dry-run"])
    assert args.batch_command == "tag"
    assert args.tag_add == "reviewed"
    assert args.dry_run is True


def test_parser_batch_protect_requires_on_or_off():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["batch", "protect"])


def test_parser_source_register():
    parser = build_parser()
    args = parser.parse_args(["source", "register", "--path", "/skills/foo", "--repo", "https://example.com/foo.git", "--ref", "main"])
    assert args.source_command == "register"
    assert args.path == "/skills/foo"
    assert args.repo == "https://example.com/foo.git"
    assert args.ref == "main"


def test_parser_upgrade_apply_dry_run():
    parser = build_parser()
    args = parser.parse_args(["upgrade", "apply", "--dry-run", "--all"])
    assert args.upgrade_command == "apply"
    assert args.dry_run is True
    assert args.apply_all is True


def test_main_active_set_max_zero_returns_2(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(tmp_path))
    code = main(["audit", "--active-set-max", "0"])
    assert code == 2


def test_parse_selectors():
    from skill_auditor.cli import _parse_selectors
    result = _parse_selectors(["ecosystem=codex", "tag=reviewed"])
    assert result == {"ecosystem": "codex", "tag": "reviewed"}


def test_parse_selectors_empty():
    from skill_auditor.cli import _parse_selectors
    assert _parse_selectors([]) == {}
    assert _parse_selectors(["noequals"]) == {}
