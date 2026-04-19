from __future__ import annotations

import json

from skill_auditor.cli import main


def invoke(argv: list[str], capsys) -> tuple[int, str, str]:
    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def test_duplicate_instances_remain_distinct_and_cluster_by_skill_key(
    tmp_path,
    monkeypatch,
    capsys,
):
    from conftest import write_codex_skill

    root = tmp_path / "skills"
    write_codex_skill(root / "copy-a", "shared-skill")
    write_codex_skill(root / "copy-b", "shared-skill")
    state_root = tmp_path / "state"
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(state_root))

    exit_code, stdout, _stderr = invoke(
        ["audit", str(root), "--ecosystem", "codex", "--format", "json"],
        capsys,
    )
    report = json.loads(stdout)
    clusters = json.loads((state_root / "clusters.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    instance_ids = [instance["instance_id"] for instance in report["instances"]]
    assert len(instance_ids) == 2
    assert len(set(instance_ids)) == 2
    assert clusters["clusters"][0]["skill_key"] == "shared-skill"
    assert len(clusters["clusters"][0]["instance_ids"]) == 2


def test_overlap_warning_generated_for_similar_descriptions(tmp_path, monkeypatch, capsys):
    from conftest import write_codex_skill

    root = tmp_path / "skills"
    write_codex_skill(root, "alpha-skill", description="Audit Python skill packages for trigger quality")
    write_codex_skill(root, "beta-skill", description="Audit Python skill packages for trigger issues")
    state_root = tmp_path / "state"
    monkeypatch.setenv("SKILL_AUDITOR_STATE_ROOT", str(state_root))

    exit_code, stdout, _stderr = invoke(
        ["audit", str(root), "--ecosystem", "codex", "--format", "json"],
        capsys,
    )
    report = json.loads(stdout)

    assert exit_code == 0
    assert any(
        finding["rule_id"] == "heuristic.overlap.lexical" for finding in report["heuristic_findings"]
    )
