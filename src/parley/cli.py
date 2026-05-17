from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from parley.context import context_seed
from parley.errors import EXIT_USAGE_OR_SCHEMA
from parley.localization import localization_add
from parley.project_init import project_init
from parley.translation import translate_project
from parley.validation import project_inspect, validate_project


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

    inspect = project_sub.add_parser("inspect")
    inspect.add_argument("--project-root")

    localization = subparsers.add_parser("localization")
    localization_sub = localization.add_subparsers(dest="localization_command")
    add = localization_sub.add_parser("add")
    add.add_argument("path")
    add.add_argument("--project-root")
    add.add_argument("--locale", required=True)
    add.add_argument("--format", choices=["ios_strings", "android_xml"])
    add.add_argument("--role", choices=["target", "authoritative"], default="target")
    add.add_argument("--id")
    add.add_argument("--status", choices=["draft", "reviewed", "approved", "locked"], default="draft")
    add.add_argument("--report-dir")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--project-root")
    validate.add_argument("--report-dir")
    validate.add_argument("--only")
    validate.set_defaults(targets=True, authoritative=True)
    targets = validate.add_mutually_exclusive_group()
    targets.add_argument("--targets", dest="targets", action="store_true")
    targets.add_argument("--no-targets", dest="targets", action="store_false")
    authoritative = validate.add_mutually_exclusive_group()
    authoritative.add_argument("--authoritative", dest="authoritative", action="store_true")
    authoritative.add_argument("--no-authoritative", dest="authoritative", action="store_false")

    translate = subparsers.add_parser("translate")
    translate.add_argument("--project-root")
    translate.add_argument("--target-locale", required=True)
    translate.add_argument("--target-path")
    translate.add_argument("--reuse-mode", choices=["tm_only", "tm_then_provider", "provider_only"], default="tm_then_provider")
    translate.add_argument("--provider", choices=["dummy", "command-json"], default="dummy")
    translate.add_argument("--provider-command")
    translate.add_argument("--provider-timeout-seconds", type=int, default=30)
    translate.add_argument("--dry-run", action="store_true")
    translate.add_argument("--no-provider", action="store_true")
    translate.add_argument("--report-dir")

    context = subparsers.add_parser("context")
    context_sub = context.add_subparsers(dest="context_command")
    seed = context_sub.add_parser("seed")
    seed.add_argument("--project-root")
    seed.add_argument("--mode", choices=["placeholder"], default="placeholder")

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
    if args.command_group == "project" and args.project_command == "inspect":
        result = project_inspect(project_root=args.project_root, cwd=Path.cwd())
        _emit_payload_or_summary(
            command="project_inspect",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        return result.exit_code
    if args.command_group == "localization" and args.localization_command == "add":
        result = localization_add(
            project_root=args.project_root,
            path=args.path,
            locale=args.locale,
            fmt=args.format,
            role=args.role,
            localization_id=args.id,
            status=args.status,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="localization_add",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "validate":
        result = validate_project(
            project_root=args.project_root,
            only_locale=args.only,
            include_targets=args.targets,
            include_authoritative=args.authoritative,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="validate",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "translate":
        result = translate_project(
            project_root=args.project_root,
            target_locale=args.target_locale,
            target_path=args.target_path,
            reuse_mode=args.reuse_mode,
            provider=args.provider,
            provider_command=args.provider_command,
            provider_timeout_seconds=args.provider_timeout_seconds,
            dry_run=args.dry_run,
            no_provider=args.no_provider,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="translate",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "context" and args.context_command == "seed":
        result = context_seed(project_root=args.project_root, mode=args.mode, cwd=Path.cwd())
        _emit_payload_or_summary(
            command="context_seed",
            result=result,
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
                        {"kind": path.parent.name, "path": str(path)}
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


def _emit_payload_or_summary(*, command: str, result, output_format: str, quiet: bool) -> None:
    if quiet:
        return
    if result.payload is not None and output_format == "json":
        print(json.dumps(result.payload, sort_keys=True))
        return
    _emit_summary(
        command=command,
        exit_code=result.exit_code,
        reports=result.reports,
        output_format=output_format,
        quiet=quiet,
    )
