from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_OK, EXIT_PROVIDER, EXIT_IO_OR_PARSER, EXIT_USAGE_OR_SCHEMA, ParleyError, UsageError
from parley.paths import localization_file_path, resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.translation import translate_project
from parley.validation import CommandResult


def translate_batch_project(
    *,
    project_root: str | None,
    target_locales: list[str] | None,
    reuse_mode: str,
    provider: str | None,
    dry_run: bool,
    no_provider: bool,
    no_context: bool,
    report_dir: str | None,
    cwd: Path,
    provider_command: str | None = None,
    provider_timeout_seconds: int | None = None,
    provider_request_delivery: str | None = None,
    provider_response_mode: str | None = None,
    write_order: str = "alphabetical",
    target_conflict_mode: str = "fail",
    progress_callback: Callable[[str, str, int, int], None] | None = None,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifact_issues = schema_issues_for_required(root, ["parley.yaml", "inventory.yaml"])
        if artifact_issues:
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], "; ".join(issue.message for issue in artifact_issues))
        artifacts = load_project_artifacts(root, include_canonical=False, include_context=False)
        selected = _selected_targets(artifacts.inventory, target_locales)
        if not selected:
            raise UsageError("no target localizations selected")
        report_root = resolve_report_dir(root, report_dir)
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))

    target_results: list[dict] = []
    reports: list[Path] = []
    for target in selected:
        target_progress_callback = None
        if progress_callback is not None:
            target_progress_callback = _target_progress_callback(progress_callback, target)
        result = translate_project(
            project_root=str(root),
            target_locale=target["locale"],
            target_path=str(localization_file_path(root, artifacts.manifest, target["path"])),
            create_target=False,
            target_format=None,
            reuse_mode=reuse_mode,
            provider=provider,
            dry_run=dry_run,
            no_provider=no_provider,
            no_context=no_context,
            report_dir=report_dir,
            cwd=cwd,
            provider_command=provider_command,
            provider_timeout_seconds=provider_timeout_seconds,
            provider_request_delivery=provider_request_delivery,
            provider_response_mode=provider_response_mode,
            write_order=write_order,
            target_conflict_mode=target_conflict_mode,
            progress_callback=target_progress_callback,
        )
        reports.extend(result.reports)
        per_target_payload = _read_report_payload(result.reports[-1]) if result.reports else None
        target_results.append(_target_result(target, result, per_target_payload))

    exit_code = _batch_exit_code([item["exit_code"] for item in target_results])
    rollup = prepare_report(
        project_root=root,
        report_dir=report_root,
        family="translation",
        canonical_command="translate_batch",
        project_id=artifacts.project_id,
        started_at=started_at,
        exit_code=exit_code,
        inputs={
            "target_locales": [_lower_ascii(item) for item in target_locales] if target_locales else None,
            "reuse_mode": reuse_mode,
            "write_order": write_order,
            "target_conflict_mode": target_conflict_mode,
            "dry_run": dry_run,
            "no_provider": no_provider,
            "no_context": no_context,
            "provider": provider,
        },
        summary=_summary(target_results, dry_run),
        findings=[],
        failure_category="target_failures" if exit_code != EXIT_OK else None,
        extra_fields={"target_results": target_results},
    )
    try:
        commit_files(root, {}, {rollup.path: rollup.content})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, reports, str(exc))
    return CommandResult(exit_code, [*reports, rollup.path])


def _target_progress_callback(
    progress_callback: Callable[[str, str, int, int], None],
    target: dict,
) -> Callable[[str, str, int, int], None]:
    prefix = f"[{target['locale']} {target['path']}]"

    def emit(key: str, source_value: str, index: int, total: int) -> None:
        progress_callback(f"{prefix} {key}", source_value, index, total)

    return emit


def _selected_targets(inventory: dict, target_locales: list[str] | None) -> list[dict]:
    locale_filter = {_lower_ascii(locale) for locale in target_locales or []}
    records = [
        record
        for record in inventory["localizations"]
        if record.get("role") == "target" and (not locale_filter or record.get("locale") in locale_filter)
    ]
    return sorted(records, key=lambda item: (item["locale"], item["path"], item["localization_id"]))


def _target_result(target: dict, result: CommandResult, payload: dict | None) -> dict:
    summary = payload.get("summary", {}) if payload else {}
    return {
        "locale": target["locale"],
        "path": target["path"],
        "localization_id": target["localization_id"],
        "exit_code": result.exit_code,
        "report": str(result.reports[-1]) if result.reports else None,
        "message": result.message,
        "key_count": summary.get("key_count", 0),
        "failed_count": summary.get("failed_count", 0),
        "reused_count": summary.get("reused_count", 0),
        "skipped_count": summary.get("skipped_count", 0),
        "generated_count": summary.get("generated_count", 0),
        "written_target": summary.get("written_target", False),
        "tm_written": summary.get("tm_written", False),
        "provider_status": summary.get("provider_status"),
    }


def _summary(target_results: list[dict], dry_run: bool) -> dict:
    return {
        "target_count": len(target_results),
        "succeeded_count": sum(1 for item in target_results if item["exit_code"] == EXIT_OK),
        "failed_count": sum(1 for item in target_results if item["exit_code"] != EXIT_OK),
        "key_count": sum(int(item["key_count"]) for item in target_results),
        "reused_count": sum(int(item["reused_count"]) for item in target_results),
        "skipped_count": sum(int(item["skipped_count"]) for item in target_results),
        "generated_count": sum(int(item["generated_count"]) for item in target_results),
        "per_key_failed_count": sum(int(item["failed_count"]) for item in target_results),
        "written_target_count": sum(1 for item in target_results if item["written_target"]),
        "tm_written_count": sum(1 for item in target_results if item["tm_written"]),
        "dry_run": dry_run,
    }


def _batch_exit_code(exit_codes: list[int]) -> int:
    if any(code == EXIT_PROVIDER for code in exit_codes):
        return EXIT_PROVIDER
    if any(code == EXIT_IO_OR_PARSER for code in exit_codes):
        return EXIT_IO_OR_PARSER
    if any(code == EXIT_USAGE_OR_SCHEMA for code in exit_codes):
        return EXIT_USAGE_OR_SCHEMA
    if any(code != EXIT_OK for code in exit_codes):
        return 1
    return EXIT_OK


def _read_report_payload(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
