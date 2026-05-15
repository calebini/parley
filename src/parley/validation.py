from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from parley.artifacts import inspect_artifacts, load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_IO_OR_PARSER, EXIT_OK, EXIT_USAGE_OR_SCHEMA, FileIOError, ParleyError, UsageError
from parley.parsers import parse_localization
from parley.paths import resolve_report_dir
from parley.reports import prepare_report, utc_now


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    reports: list[Path]
    message: str | None = None
    payload: dict | None = None


def project_inspect(*, project_root: str | None, cwd: Path) -> CommandResult:
    root = Path(project_root).absolute() if project_root else resolve_project_root(None, cwd)
    artifacts = inspect_artifacts(root)
    if any(item["status"] == "io_error" for item in artifacts):
        exit_code = EXIT_IO_OR_PARSER
    elif any(item["status"] in {"missing", "schema_invalid"} and item["kind"] == "file" for item in artifacts):
        exit_code = EXIT_USAGE_OR_SCHEMA
    else:
        exit_code = EXIT_OK
    return CommandResult(exit_code, [], payload={"project_root": str(root), "artifacts": artifacts})


def validate_project(
    *,
    project_root: str | None,
    only_locale: str | None,
    include_targets: bool,
    include_authoritative: bool,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False)
        inventory = artifacts.inventory
        records = list(inventory["localizations"])
        if sum(1 for record in records if record.get("role") == "authoritative") > 1:
            raise UsageError("inventory has multiple authoritative records", failure_category="artifact_schema")
        selected = [
            record
            for record in records
            if (include_authoritative and record.get("role") == "authoritative")
            or (include_targets and record.get("role") == "target")
        ]
        if only_locale is not None:
            normalized = _lower_ascii(only_locale)
            selected = [record for record in selected if record.get("locale") == normalized]
        selected = sorted(selected, key=lambda item: (item["locale"], item["path"], item["localization_id"]))
        if not selected:
            raise UsageError("no localization entries selected")
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))

    findings: list[dict] = []
    validated: list[dict] = []
    exit_code = EXIT_OK
    canonical = None
    canonical_issues = schema_issues_for_required(root, ["canonical-inventory.json"])
    if canonical_issues:
        exit_code = EXIT_USAGE_OR_SCHEMA
        for issue in canonical_issues:
            findings.append(_finding(issue.artifact, issue.status, issue.message, "artifact_schema", issue.status))
    else:
        try:
            canonical = load_project_artifacts(root, include_canonical=True).canonical_inventory
        except ParleyError as exc:
            exit_code = exc.exit_code
            findings.append(_finding("canonical-inventory.json", "schema_invalid", str(exc), "artifact_schema", "schema_invalid"))

    if canonical is not None and exit_code == EXIT_OK:
        canonical_entries = canonical["entries"]
        for record in selected:
            status = "validated"
            path = root / record["path"]
            try:
                content = path.read_text(encoding="utf-8")
                parsed = parse_localization(content, record["format"])
            except FileNotFoundError:
                status = "missing"
                exit_code = EXIT_IO_OR_PARSER
                findings.append(_finding(record["path"], "missing", "selected localization file is missing", "io", "missing", record))
            except OSError:
                status = "io_error"
                exit_code = EXIT_IO_OR_PARSER
                findings.append(_finding(record["path"], "io_error", "selected localization file is unreadable", "io", "io_error", record))
            except ParleyError as exc:
                status = "parse_error"
                exit_code = EXIT_IO_OR_PARSER
                findings.append(_finding(record["path"], "parse_error", str(exc), "parser", "parse_error", record))
            validated.append(_validated(record, status))
            if status != "validated":
                break
            parsed_by_key = {entry.key: entry for entry in parsed.entries}
            for key in sorted(canonical_entries):
                if key not in parsed_by_key:
                    findings.append(_finding(record["path"], "missing_key", f"missing key: {key}", "placeholder_integrity", "missing_key", record, key))
                    continue
                actual = parsed_by_key[key].placeholder_signature
                expected = canonical_entries[key].get("placeholder_signature", "")
                if actual != expected:
                    findings.append(_finding(record["path"], "placeholder_mismatch", f"placeholder mismatch for key: {key}", "placeholder_integrity", "placeholder_mismatch", record, key))
            for key in sorted(set(parsed_by_key) - set(canonical_entries)):
                findings.append(_finding(record["path"], "extra_key", f"extra key: {key}", "placeholder_integrity", "extra_key", record, key))

    if exit_code == EXIT_OK and any(item.get("severity") == "blocking" for item in findings):
        exit_code = EXIT_BLOCKING_FINDINGS
    try:
        report_root = resolve_report_dir(root, report_dir)
        report = prepare_report(
            project_root=root,
            report_dir=report_root,
            family="validation",
            canonical_command="validate",
            project_id=str(artifacts.manifest["project"]["id"]),
            started_at=started_at,
            exit_code=exit_code,
            inputs={
                "only_locale": only_locale,
                "include_targets": include_targets,
                "include_authoritative": include_authoritative,
            },
            summary={"validated_count": len(validated), "finding_count": len(findings)},
            findings=findings,
            failure_category=_failure_category(exit_code, findings),
            extra_fields={"validated_localizations": validated},
        )
        if report.path.exists():
            raise FileIOError(f"report already exists: {report.path}")
        report.path.parent.mkdir(parents=True, exist_ok=True)
        report.path.write_text(report.content, encoding="utf-8")
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))
    return CommandResult(exit_code, [report.path], payload={"validated_localizations": validated})


def _validated(record: dict, status: str) -> dict:
    return {
        "localization_id": record["localization_id"],
        "locale": record["locale"],
        "path": record["path"],
        "format": record["format"],
        "status": status,
    }


def _finding(
    path: str,
    code: str,
    message: str,
    category: str,
    failure_category: str,
    record: dict | None = None,
    key: str | None = None,
) -> dict:
    return {
        "stable_id": "|".join(str(part) for part in [path, code, key or ""]),
        "severity": "blocking",
        "category": category,
        "failure_category": failure_category,
        "path": path,
        "locale": record.get("locale") if record else None,
        "localization_id": record.get("localization_id") if record else None,
        "key": key,
        "code": code,
        "message": message,
    }


def _failure_category(exit_code: int, findings: list[dict]) -> str | None:
    if exit_code == EXIT_OK:
        return None
    if exit_code == EXIT_BLOCKING_FINDINGS:
        return "blocking_validation"
    if findings:
        return str(findings[0].get("failure_category") or "precondition_failed")
    if exit_code == EXIT_IO_OR_PARSER:
        return "io"
    return "precondition_failed"


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
