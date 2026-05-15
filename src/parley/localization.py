from __future__ import annotations

from pathlib import Path

from parley.artifacts import load_project_artifacts, read_yaml_artifact, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_IO_OR_PARSER, EXIT_OK, EXIT_USAGE_OR_SCHEMA, FileIOError, ParleyError, UsageError
from parley.hashing import sha256_canonical_json, sha256_text
from parley.parsers import infer_format, parse_localization
from parley.paths import canonical_relative_path, resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.serialization import pretty_json, yaml_dump
from parley.validation import CommandResult


def localization_add(
    *,
    project_root: str | None,
    path: str,
    locale: str,
    fmt: str | None,
    role: str,
    localization_id: str | None,
    status: str,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        report_root = resolve_report_dir(root, report_dir)
        rel_path = canonical_relative_path(root, path, cwd.absolute())
        selected_format = fmt or _format_from_inventory(root, rel_path) or infer_format(rel_path)
        if selected_format not in {"ios_strings", "android_xml"}:
            raise UsageError("unable to determine localization format")
        content = (root / rel_path).read_text(encoding="utf-8")
        parsed = parse_localization(content, selected_format)
    except OSError as exc:
        return _write_parse_failure(started_at, project_root, cwd, report_dir, path, str(exc), "io")
    except ParleyError as exc:
        if exc.exit_code == EXIT_IO_OR_PARSER and project_root:
            return _write_parse_failure(started_at, project_root, cwd, report_dir, path, str(exc), exc.failure_category)
        return CommandResult(exc.exit_code, [], str(exc))

    findings: list[dict] = []
    try:
        artifact_issues = schema_issues_for_required(root, ["inventory.yaml", "canonical-inventory.json"])
        if role == "authoritative":
            artifact_issues.extend(schema_issues_for_required(root, ["parley.yaml"]))
        if artifact_issues:
            for issue in artifact_issues:
                findings.append(_finding(issue.artifact, issue.status, issue.message, "artifact_schema", issue.status))
            report = _validation_report(root, report_root, started_at, EXIT_USAGE_OR_SCHEMA, findings, [])
            _write_report_only(report)
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [report.path])
        artifacts = load_project_artifacts(root, include_canonical=True)
        inventory = artifacts.inventory
        manifest = artifacts.manifest
        canonical = artifacts.canonical_inventory
        normalized_locale = _lower_ascii(locale)
        effective_id = localization_id or f"{normalized_locale}::{rel_path}"
        records = list(inventory["localizations"])
        existing = next((record for record in records if record["localization_id"] == effective_id), None)
        authoritative_records = [record for record in records if record["role"] == "authoritative"]
        if role == "authoritative" and authoritative_records and authoritative_records[0]["localization_id"] != effective_id:
            findings.append(_finding(rel_path, "authoritative_conflict", "authoritative localization already exists", "artifact_schema", "precondition_failed"))
            report = _validation_report(root, report_root, started_at, EXIT_USAGE_OR_SCHEMA, findings, [])
            _write_report_only(report)
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [report.path])
        if existing:
            if existing["path"] != rel_path or existing["locale"] != normalized_locale:
                findings.append(_finding(rel_path, "immutable_field_change", "existing localization path or locale is immutable", "artifact_schema", "precondition_failed", existing))
                report = _validation_report(root, report_root, started_at, EXIT_USAGE_OR_SCHEMA, findings, [])
                _write_report_only(report)
                return CommandResult(EXIT_USAGE_OR_SCHEMA, [report.path])
            existing["format"] = selected_format if fmt else existing["format"]
            existing["status"] = status
            if role == "authoritative":
                existing["role"] = "authoritative"
            existing["parser"] = selected_format
            existing["last_observed_hash"] = parsed.normalized_hash
        else:
            records.append(
                {
                    "localization_id": effective_id,
                    "locale": normalized_locale,
                    "format": selected_format,
                    "path": rel_path,
                    "role": role,
                    "status": status,
                    "parser": selected_format,
                    "last_observed_hash": parsed.normalized_hash,
                }
            )
        inventory["localizations"] = sorted(records, key=lambda item: (item["locale"], item["path"], item["localization_id"]))
        files = {root / "inventory.yaml": yaml_dump(inventory).encode("utf-8")}
        if role == "authoritative" or effective_id == manifest["project"]["authoritative_localization_id"]:
            manifest["project"]["authoritative_localization_id"] = effective_id
            manifest["project"]["authoritative_locale"] = normalized_locale
            canonical = _canonical_inventory(
                project_id=manifest["project"]["id"],
                localization_id=effective_id,
                locale=normalized_locale,
                fmt=selected_format,
                parsed_entries=parsed.entries,
                generated_at=started_at,
                previous=canonical,
            )
            files[root / "parley.yaml"] = yaml_dump(manifest).encode("utf-8")
            files[root / "canonical-inventory.json"] = pretty_json(canonical).encode("utf-8")
        structural_findings = _structural_findings(rel_path, inventory["localizations"][-1] if False else next(record for record in inventory["localizations"] if record["localization_id"] == effective_id), parsed, canonical)
        findings.extend(structural_findings)
        exit_code = EXIT_BLOCKING_FINDINGS if findings else EXIT_OK
        report = _validation_report(root, report_root, started_at, exit_code, findings, [_validated(next(record for record in inventory["localizations"] if record["localization_id"] == effective_id), "validated")])
        commit_files(root, files, {report.path: report.content})
        return CommandResult(exit_code, [report.path])
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def _format_from_inventory(root: Path, rel_path: str) -> str | None:
    try:
        artifacts = load_project_artifacts(root, include_canonical=False)
    except ParleyError:
        return None
    for record in artifacts.inventory.get("localizations", []):
        if record.get("path") == rel_path:
            return str(record.get("format"))
    return None


def _write_parse_failure(started_at: str, project_root: str | None, cwd: Path, report_dir: str | None, path: str, message: str, category: str) -> CommandResult:
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False)
        report_root = resolve_report_dir(root, report_dir)
        finding = _finding(path, "parse_error" if category == "parser" else "io_error", message, category, category)
        report = _validation_report(root, report_root, started_at, EXIT_IO_OR_PARSER, [finding], [])
        _write_report_only(report)
        return CommandResult(EXIT_IO_OR_PARSER, [report.path], message)
    except ParleyError:
        return CommandResult(EXIT_IO_OR_PARSER, [], message)


def _write_report_only(report) -> None:
    if report.path.exists():
        raise FileIOError(f"report already exists: {report.path}")
    report.path.parent.mkdir(parents=True, exist_ok=True)
    report.path.write_text(report.content, encoding="utf-8")


def _validation_report(root: Path, report_root: Path, started_at: str, exit_code: int, findings: list[dict], validated: list[dict]):
    project_id = "unknown"
    try:
        project_id = str(read_yaml_artifact(root / "parley.yaml").get("project", {}).get("id") or "unknown")
    except ParleyError:
        pass
    return prepare_report(
        project_root=root,
        report_dir=report_root,
        family="validation",
        canonical_command="localization_add",
        project_id=project_id,
        started_at=started_at,
        exit_code=exit_code,
        inputs={},
        summary={"validated_count": len(validated), "finding_count": len(findings)},
        findings=findings,
        failure_category=None if exit_code == EXIT_OK else ("blocking_validation" if exit_code == EXIT_BLOCKING_FINDINGS else "precondition_failed"),
        extra_fields={"validated_localizations": validated},
    )


def _canonical_inventory(*, project_id: str, localization_id: str, locale: str, fmt: str, parsed_entries: list, generated_at: str, previous: dict | None) -> dict:
    previous_entries = (previous or {}).get("entries", {}) if isinstance(previous, dict) else {}
    entries = {}
    inventory_hash_entries = {}
    for entry in sorted(parsed_entries, key=lambda item: item.key):
        content_input = {
            "key": entry.key,
            "value": entry.value,
            "locale": locale,
            "format": fmt,
            "placeholder_signature": entry.placeholder_signature,
        }
        content_hash = sha256_canonical_json(content_input)
        previous_entry = previous_entries.get(entry.key, {})
        first_seen = previous_entry.get("first_seen_at", generated_at)
        last_updated = previous_entry.get("last_updated_at", generated_at)
        if previous_entry.get("content_hash") != content_hash:
            last_updated = generated_at
        entries[entry.key] = {
            "key": entry.key,
            "authoritative_value": entry.value,
            "value_hash": sha256_text(entry.value),
            "content_hash": content_hash,
            "placeholder_signature": entry.placeholder_signature,
            "placeholders": entry.placeholders,
            "first_seen_at": first_seen,
            "last_updated_at": last_updated,
        }
        inventory_hash_entries[entry.key] = {
            "authoritative_value": entry.value,
            "placeholder_signature": entry.placeholder_signature,
        }
    return {
        "schema_version": "1.0",
        "project_id": project_id,
        "authoritative_localization_id": localization_id,
        "authoritative_locale": locale,
        "authoritative_format": fmt,
        "generated_at": generated_at,
        "inventory_hash": sha256_canonical_json({"authoritative_locale": locale, "authoritative_format": fmt, "entries": inventory_hash_entries}),
        "entries": entries,
    }


def _structural_findings(path: str, record: dict, parsed, canonical: dict | None) -> list[dict]:
    if not canonical:
        return []
    findings = []
    canonical_entries = canonical["entries"]
    parsed_by_key = {entry.key: entry for entry in parsed.entries}
    for key in sorted(canonical_entries):
        if key not in parsed_by_key:
            findings.append(_finding(path, "missing_key", f"missing key: {key}", "placeholder_integrity", "missing_key", record, key))
            continue
        if parsed_by_key[key].placeholder_signature != canonical_entries[key].get("placeholder_signature", ""):
            findings.append(_finding(path, "placeholder_mismatch", f"placeholder mismatch for key: {key}", "placeholder_integrity", "placeholder_mismatch", record, key))
    for key in sorted(set(parsed_by_key) - set(canonical_entries)):
        findings.append(_finding(path, "extra_key", f"extra key: {key}", "placeholder_integrity", "extra_key", record, key))
    return findings


def _validated(record: dict, status: str) -> dict:
    return {
        "localization_id": record["localization_id"],
        "locale": record["locale"],
        "path": record["path"],
        "format": record["format"],
        "status": status,
    }


def _finding(path: str, code: str, message: str, category: str, failure_category: str, record: dict | None = None, key: str | None = None) -> dict:
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


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
