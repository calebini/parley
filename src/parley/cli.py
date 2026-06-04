from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from parley.context import context_validate
from parley.errors import EXIT_USAGE_OR_SCHEMA
from parley.glossary import glossary_import, glossary_init, glossary_list, glossary_suggest_from_tm, glossary_validate
from parley.locale_reference import locale_reference_list
from parley.localization import localization_add, localization_list
from parley.project_init import project_init
from parley.translation import translate_project
from parley.translation_memory import import_target_to_memory
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
    list_localizations = localization_sub.add_parser("list")
    list_localizations.add_argument("--project-root")

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
    translate.add_argument("--create-target", action="store_true")
    translate.add_argument("--format", choices=["ios_strings", "android_xml"])
    translate.add_argument("--reuse-mode", choices=["tm_only", "tm_then_provider", "provider_only"], default="tm_then_provider")
    translate.add_argument("--provider", default="dummy")
    translate.add_argument("--provider-command")
    translate.add_argument("--provider-timeout-seconds", type=int)
    translate.add_argument("--provider-request-delivery", choices=["stdin_json", "output_file"])
    translate.add_argument("--provider-response-mode", choices=["stdout_json", "stdout_json_envelope", "output_file_json"])
    translate.add_argument("--dry-run", action="store_true")
    translate.add_argument("--no-provider", action="store_true")
    translate.add_argument("--no-context", action="store_true")
    translate.add_argument("--report-dir")

    tm = subparsers.add_parser("tm")
    tm_sub = tm.add_subparsers(dest="tm_command")
    import_target = tm_sub.add_parser("import-target")
    import_target.add_argument("--project-root")
    import_target.add_argument("--target-locale", required=True)
    import_target.add_argument("--target-path")
    import_target.add_argument("--status", choices=["draft", "reviewed", "approved", "locked"], default="reviewed")
    import_target.add_argument("--dry-run", action="store_true")
    import_target.add_argument("--report-dir")

    locale = subparsers.add_parser("locale")
    locale_sub = locale.add_subparsers(dest="locale_command")
    locale_list = locale_sub.add_parser("list")
    locale_list.add_argument("--query")

    glossary = subparsers.add_parser("glossary")
    glossary_sub = glossary.add_subparsers(dest="glossary_command")
    glossary_init_parser = glossary_sub.add_parser("init")
    glossary_init_parser.add_argument("--project-root")
    glossary_init_parser.add_argument("--force", action="store_true")
    glossary_init_parser.add_argument("--with-example", action="store_true")
    glossary_init_parser.add_argument("--report-dir")
    glossary_import_parser = glossary_sub.add_parser("import")
    glossary_import_parser.add_argument("--project-root")
    glossary_import_parser.add_argument("--file", required=True)
    glossary_import_parser.add_argument("--merge-mode", choices=["replace", "merge"], default="replace")
    glossary_import_parser.add_argument("--report-dir")
    glossary_list_parser = glossary_sub.add_parser("list")
    glossary_list_parser.add_argument("--project-root")
    glossary_list_parser.add_argument("--locale")
    glossary_list_parser.add_argument("--query")
    glossary_validate_parser = glossary_sub.add_parser("validate")
    glossary_validate_parser.add_argument("--project-root")
    glossary_validate_parser.add_argument("--report-dir")
    glossary_suggest_parser = glossary_sub.add_parser("suggest")
    glossary_suggest_parser.add_argument("--project-root")
    glossary_suggest_parser.add_argument("--from-tm", action="store_true", required=True)
    glossary_suggest_parser.add_argument("--target-locale")
    glossary_suggest_parser.add_argument("--report-dir")

    context = subparsers.add_parser("context")
    context_sub = context.add_subparsers(dest="context_command")
    context_validate_parser = context_sub.add_parser("validate")
    context_validate_parser.add_argument("--project-root")
    context_validate_parser.add_argument("--report-dir")

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
    if args.command_group == "localization" and args.localization_command == "list":
        result = localization_list(project_root=args.project_root, cwd=Path.cwd())
        if args.output_format == "json":
            _emit_payload_or_summary(
                command="localization_list",
                result=result,
                output_format=args.output_format,
                quiet=args.quiet,
            )
        elif not args.quiet:
            _emit_localization_table(result)
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
        progress_callback = None
        if not args.quiet and args.output_format == "text":
            progress_callback = _emit_translate_progress
        result = translate_project(
            project_root=args.project_root,
            target_locale=args.target_locale,
            target_path=args.target_path,
            create_target=args.create_target,
            target_format=args.format,
            reuse_mode=args.reuse_mode,
            provider=args.provider,
            provider_command=args.provider_command,
            provider_timeout_seconds=args.provider_timeout_seconds,
            provider_request_delivery=args.provider_request_delivery,
            provider_response_mode=args.provider_response_mode,
            dry_run=args.dry_run,
            no_provider=args.no_provider,
            no_context=args.no_context,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
            progress_callback=progress_callback,
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
    if args.command_group == "tm" and args.tm_command == "import-target":
        result = import_target_to_memory(
            project_root=args.project_root,
            target_locale=args.target_locale,
            target_path=args.target_path,
            status=args.status,
            dry_run=args.dry_run,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="tm_import_target",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "locale" and args.locale_command == "list":
        result = locale_reference_list(query=args.query)
        if args.output_format == "json":
            _emit_payload_or_summary(
                command="locale_list",
                result=result,
                output_format=args.output_format,
                quiet=args.quiet,
            )
        elif not args.quiet:
            _emit_locale_reference_table(result)
        return result.exit_code
    if args.command_group == "glossary" and args.glossary_command == "import":
        result = glossary_import(
            project_root=args.project_root,
            file=args.file,
            merge_mode=args.merge_mode,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="glossary_import",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "glossary" and args.glossary_command == "init":
        result = glossary_init(
            project_root=args.project_root,
            force=args.force,
            with_example=args.with_example,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="glossary_init",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "glossary" and args.glossary_command == "list":
        result = glossary_list(project_root=args.project_root, locale=args.locale, query=args.query, cwd=Path.cwd())
        if args.output_format == "json":
            _emit_payload_or_summary(
                command="glossary_list",
                result=result,
                output_format=args.output_format,
                quiet=args.quiet,
            )
        elif not args.quiet:
            _emit_glossary_table(result)
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "glossary" and args.glossary_command == "validate":
        result = glossary_validate(project_root=args.project_root, report_dir=args.report_dir, cwd=Path.cwd())
        _emit_payload_or_summary(
            command="glossary_validate",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "glossary" and args.glossary_command == "suggest":
        result = glossary_suggest_from_tm(
            project_root=args.project_root,
            target_locale=args.target_locale,
            report_dir=args.report_dir,
            cwd=Path.cwd(),
        )
        _emit_payload_or_summary(
            command="glossary_suggest",
            result=result,
            output_format=args.output_format,
            quiet=args.quiet,
        )
        if result.message:
            print(result.message, file=sys.stderr)
        return result.exit_code
    if args.command_group == "context" and args.context_command == "validate":
        result = context_validate(project_root=args.project_root, report_dir=args.report_dir, cwd=Path.cwd())
        _emit_payload_or_summary(
            command="context_validate",
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


def _emit_translate_progress(key: str, source_value: str, index: int, total: int) -> None:
    preview = _single_line_preview(source_value, limit=72)
    print(f"translating {index}/{total} {key}: {preview}", file=sys.stderr, flush=True)


def _single_line_preview(value: str, *, limit: int) -> str:
    preview = " ".join(value.split())
    if len(preview) <= limit:
        return preview
    return preview[: limit - 3] + "..."


def _emit_localization_table(result) -> None:
    if result.payload is None:
        _emit_summary(
            command="localization_list",
            exit_code=result.exit_code,
            reports=result.reports,
            output_format="text",
            quiet=False,
        )
        return
    rows = result.payload.get("localizations", [])
    if not rows:
        print("No localizations registered.")
        return
    columns = ["locale", "role", "format", "status", "path", "localization_id"]
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def _emit_locale_reference_table(result) -> None:
    if result.payload is None:
        _emit_summary(
            command="locale_list",
            exit_code=result.exit_code,
            reports=result.reports,
            output_format="text",
            quiet=False,
        )
        return
    rows = result.payload.get("locales", [])
    if not rows:
        print("No locale suggestions matched.")
        return
    columns = ["language", "locale", "stored_locale", "ios_lproj", "android_values"]
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def _emit_glossary_table(result) -> None:
    if result.payload is None:
        _emit_summary(
            command="glossary_list",
            exit_code=result.exit_code,
            reports=result.reports,
            output_format="text",
            quiet=False,
        )
        return
    rows = result.payload.get("terms", [])
    if not rows:
        print("No glossary terms.")
        return
    columns = ["id", "source", "target_locale", "target", "status", "protected", "untranslated", "forbidden"]
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))
