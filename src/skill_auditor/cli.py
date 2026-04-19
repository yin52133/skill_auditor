from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import run_audit
from .errors import SkillAuditorError
from .hooks import install_hooks, run_hook_command
from .reporting import render_report
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

    hook_run = subparsers.add_parser("hook-run")
    hook_run.add_argument("--repo", required=True)
    hook_run.add_argument("--hook", required=True)
    hook_run.add_argument(
        "--ecosystem",
        choices=["host", "codex", "claude", "both"],
        default="host",
    )

    return parser


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
            install_hooks(Path(args.repo).expanduser().resolve())
            return 0

        if args.command == "hook-run":
            return run_hook_command(
                repo=Path(args.repo).expanduser().resolve(),
                hook_name=args.hook,
                ecosystem_request=args.ecosystem,
            )
    except SkillAuditorError as exc:
        _print_error(exc)
        return 2

    raise SkillAuditorError("ENGINE_BROKEN", "ENGINE_BROKEN: reached unreachable CLI branch.")
