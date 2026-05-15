from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from parley.errors import EXIT_USAGE_OR_SCHEMA
from parley.project_init import project_init


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parley")
    parser.add_argument("--output-format", choices=["text", "json"], default="text")
    parser.add_argument("--quiet", action="store_true")
    subparsers = parser.add_subparsers(dest="command_group")

    project = subparsers.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command")
    init = project_sub.add_parser("init")
    init.add_argument("--project-root")
    init.add_argument("--name", required=True)
    init.add_argument("--authoritative", required=True)
    init.add_argument("--locale", required=True)
    init.add_argument("--format", choices=["ios_strings", "android_xml"])
    init.add_argument("--force", action="store_true")
    init.add_argument("--report-dir")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command_group == "project" and args.project_command == "init":
        project_root = Path(args.project_root) if args.project_root else Path.cwd()
        result = project_init(
            project_root=project_root,
            name=args.name,
            authoritative=args.authoritative,
            locale=args.locale,
            fmt=args.format,
            force=args.force,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_summary(
            command="project_init",
            exit_code=result.exit_code,
            reports=result.reports,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code

    parser.print_help(sys.stderr)
    return EXIT_USAGE_OR_SCHEMA


def _emit_summary(
    *,
    command: str,
    exit_code: int,
    reports: list[Path],
    output_format: str,
    quiet: bool,
) -> None:
    if quiet:
        return
    if output_format == "json":
        print(
            json.dumps(
                {
                    "command": command,
                    "exit_code": exit_code,
                    "reports": [
                        {"kind": "validation", "path": str(path)}
                        for path in sorted(reports, key=lambda item: str(item))
                    ],
                },
                sort_keys=True,
            )
        )
        return
    print(f"command={command}")
    print(f"exit_code={exit_code}")
    print(f"reports_written={len(reports)}")
    for path in sorted(reports, key=lambda item: str(item)):
        print(f"report={path}")

