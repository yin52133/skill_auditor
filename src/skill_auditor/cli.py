from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .batch import batch_edit
from .engine import run_audit
from .errors import SkillAuditorError
from .hooks import install_hooks, install_claude_hooks, run_hook_command
from .reporting import render_report
from .sources import detect_all_sources, list_sources, register_source
from .state import StateManager
from .upgrade import apply_upgrade, check_upgrades
from .utils import atomic_write_text
from .watch import run_watch_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-auditor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("paths", nargs="*")
    audit_parser.add_argument("--all", action="store_true")
    audit_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    audit_parser.add_argument("--language", choices=["en", "zh"], default="en")
    audit_parser.add_argument("--output", help="Write the rendered report to this file path atomically.")
    audit_parser.add_argument(
        "--ecosystem",
        choices=["host", "codex", "claude", "both"],
        default="host",
    )
    audit_parser.add_argument("--active-set-max", type=int, default=30)

    watch_parser = subparsers.add_parser("watch")
    watch_parser.add_argument("paths", nargs="*")
    watch_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    watch_parser.add_argument("--language", choices=["en", "zh"], default="en")
    watch_parser.add_argument(
        "--ecosystem",
        choices=["host", "codex", "claude", "both"],
        default="host",
    )

    hooks_parser = subparsers.add_parser("hooks")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command", required=True)
    hooks_install = hooks_subparsers.add_parser("install")
    hooks_install.add_argument("--repo", required=True)

    hooks_install_claude = hooks_subparsers.add_parser("install-claude")
    hooks_install_claude.add_argument("--scope", choices=["user", "project"], default="user")

    hook_run = subparsers.add_parser("hook-run")
    hook_run.add_argument("--repo", required=True)
    hook_run.add_argument("--hook", required=True)
    hook_run.add_argument(
        "--ecosystem",
        choices=["host", "codex", "claude", "both"],
        default="host",
    )

    # --- batch subcommands ---
    batch_parser = subparsers.add_parser("batch")
    batch_sub = batch_parser.add_subparsers(dest="batch_command", required=True)

    tag_p = batch_sub.add_parser("tag")
    tag_p.add_argument("--add", dest="tag_add")
    tag_p.add_argument("--remove", dest="tag_remove")
    tag_p.add_argument("--selector", action="append", dest="selectors", default=[])
    tag_p.add_argument("--include-protected", action="store_true")
    tag_p.add_argument("--include-builtin", action="store_true")
    tag_p.add_argument("--dry-run", action="store_true")

    note_p = batch_sub.add_parser("note")
    note_p.add_argument("--set", dest="note_value", required=True)
    note_p.add_argument("--selector", action="append", dest="selectors", default=[])
    note_p.add_argument("--include-protected", action="store_true")
    note_p.add_argument("--include-builtin", action="store_true")
    note_p.add_argument("--dry-run", action="store_true")

    protect_p = batch_sub.add_parser("protect")
    protect_grp = protect_p.add_mutually_exclusive_group(required=True)
    protect_grp.add_argument("--on", dest="protect_on", action="store_true")
    protect_grp.add_argument("--off", dest="protect_off", action="store_true")
    protect_p.add_argument("--selector", action="append", dest="selectors", default=[])

    allow_p = batch_sub.add_parser("allow-rule")
    allow_p.add_argument("--add", dest="rule_add")
    allow_p.add_argument("--remove", dest="rule_remove")
    allow_p.add_argument("--selector", action="append", dest="selectors", default=[])
    allow_p.add_argument("--include-protected", action="store_true")
    allow_p.add_argument("--include-builtin", action="store_true")
    allow_p.add_argument("--dry-run", action="store_true")

    # --- source subcommands ---
    source_parser = subparsers.add_parser("source")
    source_sub = source_parser.add_subparsers(dest="source_command", required=True)

    source_list = source_sub.add_parser("list")
    source_list.add_argument("--format", choices=["text", "json"], default="text")

    source_reg = source_sub.add_parser("register")
    source_reg.add_argument("--path", required=True)
    source_reg.add_argument("--repo", required=True)
    source_reg.add_argument("--ref")

    source_detect = source_sub.add_parser("detect")
    source_detect.add_argument("paths", nargs="*")
    source_detect.add_argument("--all", action="store_true", dest="detect_all")
    source_detect.add_argument(
        "--ecosystem",
        choices=["host", "codex", "claude", "both"],
        default=None,
    )

    # --- upgrade subcommands ---
    upgrade_parser = subparsers.add_parser("upgrade")
    upgrade_sub = upgrade_parser.add_subparsers(dest="upgrade_command", required=True)

    upgrade_check = upgrade_sub.add_parser("check")
    upgrade_check.add_argument("--all", action="store_true", dest="upgrade_all")
    upgrade_check.add_argument("--format", choices=["text", "json"], default="text")

    upgrade_apply = upgrade_sub.add_parser("apply")
    upgrade_apply.add_argument("instance_ids", nargs="*")
    upgrade_apply.add_argument("--all", action="store_true", dest="apply_all")
    upgrade_apply.add_argument("--dry-run", action="store_true")

    return parser


def _parse_selectors(selectors: list[str]) -> dict:
    result = {}
    for item in selectors:
        if "=" in item:
            k, v = item.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _handle_batch(args: argparse.Namespace) -> int:
    state = StateManager()
    selector = _parse_selectors(getattr(args, "selectors", []) or [])
    include_protected = getattr(args, "include_protected", False)
    include_builtin = getattr(args, "include_builtin", False)
    dry_run = getattr(args, "dry_run", False)
    operations: list[dict] = []

    if args.batch_command == "tag":
        if args.tag_add:
            operations.append({"op": "add_tag", "value": args.tag_add})
        if args.tag_remove:
            operations.append({"op": "remove_tag", "value": args.tag_remove})
    elif args.batch_command == "note":
        operations.append({"op": "set_note", "value": args.note_value})
    elif args.batch_command == "protect":
        operations.append({"op": "set_sync_protected", "value": args.protect_on})
        include_protected = True
        include_builtin = False
    elif args.batch_command == "allow-rule":
        if args.rule_add:
            operations.append({"op": "add_rule_exception", "value": args.rule_add})
        if args.rule_remove:
            operations.append({"op": "remove_rule_exception", "value": args.rule_remove})

    if not operations:
        print("No operations specified.", file=sys.stderr)
        return 2

    result = batch_edit(
        state,
        selector=selector or None,
        operations=operations,
        include_protected=include_protected,
        include_builtin=include_builtin,
        dry_run=dry_run,
    )
    tag = "[dry-run] " if dry_run else ""
    print(f"{tag}applied: {len(result.applied)}, skipped_protected: {len(result.skipped_protected)}, "
          f"skipped_builtin: {len(result.skipped_builtin)}, skipped_missing: {len(result.skipped_missing)}, "
          f"failed: {len(result.failed)}")
    if result.failed:
        for iid, err in result.failed:
            print(f"  FAILED {iid}: {err}", file=sys.stderr)
    return 0


def _handle_source(args: argparse.Namespace) -> int:
    state = StateManager()

    if args.source_command == "list":
        sources = list_sources(state)
        if args.format == "json":
            print(json.dumps(sources, indent=2))
        else:
            for item in sources:
                print(f"{item['instance_id']:40s}  {item['source_kind']:20s}  {item['source'].get('url', '')}")
        return 0

    if args.source_command == "register":
        from .discovery import infer_path_ecosystem
        from .utils import make_instance_id
        skill_path = Path(args.path).expanduser().resolve()
        eco = infer_path_ecosystem(skill_path)
        instance_id = make_instance_id(eco, skill_path)
        ok = register_source(state, instance_id, args.repo, ref=args.ref)
        if ok:
            print(f"Registered {instance_id} → {args.repo}")
        else:
            print(f"Instance {instance_id} not found in ledger; run 'skill-auditor audit' first.", file=sys.stderr)
            return 1
        return 0

    if args.source_command == "detect":
        eco = getattr(args, "ecosystem", None)
        results = detect_all_sources(ecosystem=eco)
        for item in results:
            git_url = (item.get("git_info") or {}).get("url", "")
            print(f"{item['path']:60s}  {item['source_kind']:20s}  {git_url}")
        return 0

    return 0


def _handle_upgrade(args: argparse.Namespace) -> int:
    if args.upgrade_command == "check":
        candidates = check_upgrades()
        if args.format == "json":
            from dataclasses import asdict
            print(json.dumps([asdict(c) for c in candidates], indent=2))
        else:
            if not candidates:
                print("No upgrades available.")
            else:
                for c in candidates:
                    status = "↑ update available" if c.remote_commit and c.remote_commit != c.current_commit else "✓ up to date"
                    print(f"{c.instance_id or c.skill_key:40s}  {status}")
                    if c.diff_summary:
                        print(f"  {c.diff_summary}")
        return 0

    if args.upgrade_command == "apply":
        instance_ids = args.instance_ids if not args.apply_all else None
        candidates = check_upgrades(instance_ids=instance_ids)
        if not candidates:
            print("No upgrade candidates found.")
            return 0
        for c in candidates:
            print(f"Upgrading {c.skill_key} from {c.remote_url}…")
            ok, new_fp, err = apply_upgrade(c, dry_run=args.dry_run)
            if ok:
                if args.dry_run:
                    print(f"  [dry-run] would upgrade, new fingerprint: {new_fp}")
                else:
                    print(f"  Done, new fingerprint: {new_fp}")
            else:
                print(f"  FAILED: {err}", file=sys.stderr)
        return 0

    return 0


def _print_error(exc: SkillAuditorError) -> None:
    print(exc.message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "audit":
            if args.active_set_max <= 0:
                raise SkillAuditorError(
                    "INVALID_ARGUMENT",
                    "INVALID_ARGUMENT: --active-set-max must be greater than zero.",
                )
            report, exit_code = run_audit(
                paths=args.paths,
                use_all=args.all,
                ecosystem_request=args.ecosystem,
                output_format=args.format,
                active_set_max=args.active_set_max,
                audit_mode="manual",
                write_state=True,
                include_heuristics=True,
            )
            rendered = render_report(report, args.format, language=args.language)
            if args.output:
                persisted = rendered if rendered.endswith("\n") else rendered + "\n"
                atomic_write_text(Path(args.output).expanduser().resolve(), persisted)
            print(rendered)
            return exit_code

        if args.command == "watch":
            return run_watch_loop(
                paths=args.paths,
                ecosystem_request=args.ecosystem,
                output_format=args.format,
            )

        if args.command == "hooks":
            if args.hooks_command == "install":
                install_hooks(Path(args.repo).expanduser().resolve())
            elif args.hooks_command == "install-claude":
                settings_path = install_claude_hooks(args.scope)
                print(f"Claude Code hooks installed. Settings: {settings_path}")
            return 0

        if args.command == "hook-run":
            return run_hook_command(
                repo=Path(args.repo).expanduser().resolve(),
                hook_name=args.hook,
                ecosystem_request=args.ecosystem,
            )

        if args.command == "batch":
            return _handle_batch(args)

        if args.command == "source":
            return _handle_source(args)

        if args.command == "upgrade":
            return _handle_upgrade(args)
    except SkillAuditorError as exc:
        _print_error(exc)
        return 2

    raise SkillAuditorError("ENGINE_BROKEN", "ENGINE_BROKEN: reached unreachable CLI branch.")
