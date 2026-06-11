from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_IO_OR_PARSER, EXIT_OK, EXIT_USAGE_OR_SCHEMA, ParleyError
from parley.parsers import ParsedEntry, ParserError, parse_localization
from parley.paths import localization_file_path, resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.validation import CommandResult


@dataclass(frozen=True)
class Fix:
    path: Path
    rel_path: str
    locale: str
    localization_id: str
    key: str
    old_value: str
    new_value: str
    fmt: str


MOJIBAKE_PATTERNS = ("Ã", "Â", "â\x80", "\ufffd")
SOURCE_EQUAL_ALLOWLIST = {
    "Label",
    "Product_Name",
    "License_Policy_URL",
    "Privacy_Policy_URL",
    "Eula_File_Name",
    "Privacy_Policy_File_Name",
}


def lint_audit(*, project_root: str | None, profile: str, scope: str, report_dir: str | None, cwd: Path) -> CommandResult:
    return _lint(project_root=project_root, profile=profile, scope=scope, fix=False, dry_run=True, report_dir=report_dir, cwd=cwd)


def lint_fix(*, project_root: str | None, profile: str, scope: str, dry_run: bool, report_dir: str | None, cwd: Path) -> CommandResult:
    return _lint(project_root=project_root, profile=profile, scope=scope, fix=True, dry_run=dry_run, report_dir=report_dir, cwd=cwd)


def _lint(
    *,
    project_root: str | None,
    profile: str,
    scope: str,
    fix: bool,
    dry_run: bool,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    if profile not in {"basic", "release"}:
        return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"unsupported lint profile: {profile}")
    if scope not in {"files", "tm", "all"}:
        return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"unsupported lint scope: {scope}")
    try:
        root = resolve_project_root(project_root, cwd)
        artifact_issues = schema_issues_for_required(root, ["parley.yaml", "inventory.yaml", "canonical-inventory.json"])
        if artifact_issues:
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], "; ".join(issue.message for issue in artifact_issues))
        artifacts = load_project_artifacts(root, include_canonical=True, include_context=False)
        assert artifacts.canonical_inventory is not None
        report_root = resolve_report_dir(root, report_dir)
        findings: list[dict] = []
        fixes: list[Fix] = []
        scanned = 0
        tm_scanned = 0
        if scope in {"files", "all"}:
            findings, fixes, scanned = _audit_localizations(root, artifacts.manifest, artifacts.inventory, artifacts.canonical_inventory, profile)
        if scope in {"tm", "all"}:
            tm_findings, tm_fixes, tm_scanned = _audit_translation_memory(root, artifacts.manifest, artifacts.project_id)
            findings.extend(tm_findings)
            fixes.extend(tm_fixes)
        applied_count = 0
        files: dict[Path, bytes] = {}
        if fix and fixes and not dry_run:
            files = _fixed_files(fixes)
            tm_path = root / artifacts.manifest["artifacts"]["translation_memory"]
            if tm_path.exists():
                files[tm_path] = _tm_bytes_after_fixes(tm_path, fixes)
            applied_count = len(fixes)
            if files:
                commit_files(root, files, {})
        remaining_findings = findings
        if fix and fixes and not dry_run:
            remaining_findings = []
            if scope in {"files", "all"}:
                remaining_findings, _, _ = _audit_localizations(
                    root,
                    artifacts.manifest,
                    artifacts.inventory,
                    artifacts.canonical_inventory,
                    profile,
                )
            if scope in {"tm", "all"}:
                tm_remaining, _, _ = _audit_translation_memory(root, artifacts.manifest, artifacts.project_id)
                remaining_findings.extend(tm_remaining)
        exit_code = EXIT_BLOCKING_FINDINGS if remaining_findings else EXIT_OK
        report = prepare_report(
            project_root=root,
            report_dir=report_root,
            family="lint",
            canonical_command="lint_fix" if fix else "lint_audit",
            project_id=artifacts.project_id,
            started_at=started_at,
            exit_code=exit_code,
            inputs={"profile": profile, "scope": scope, "fix": fix, "dry_run": dry_run},
            summary={
                "profile": profile,
                "scope": scope,
                "mode": "fix" if fix else "audit",
                "dry_run": dry_run,
                "localization_count": scanned,
                "tm_record_count": tm_scanned,
                "finding_count": len(remaining_findings),
                "fixable_count": len(fixes),
                "applied_count": applied_count,
                "warning_count": sum(1 for item in remaining_findings if item.get("severity") == "warning"),
                "error_count": sum(1 for item in remaining_findings if item.get("severity") == "error"),
            },
            findings=remaining_findings,
            failure_category="lint_findings" if remaining_findings else None,
        )
        commit_files(root, {}, {report.path: report.content})
        return CommandResult(exit_code, [report.path], payload={"findings": remaining_findings, "fixes": [fix_to_payload(item) for item in fixes]})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))
    except sqlite3.DatabaseError as exc:
        return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"invalid translation-memory.sqlite: {exc}")


def _audit_localizations(
    root: Path,
    manifest: dict,
    inventory: dict,
    canonical: dict,
    profile: str,
) -> tuple[list[dict], list[Fix], int]:
    findings: list[dict] = []
    fixes: list[Fix] = []
    source_entries = _source_entries(canonical)
    source_keys = set(source_entries)
    scanned = 0
    for record in inventory["localizations"]:
        scanned += 1
        path = localization_file_path(root, manifest, record["path"])
        try:
            parsed = parse_localization(path.read_text(encoding="utf-8"), record["format"])
        except OSError as exc:
            findings.append(_finding(record=record, code="localization_io_error", category="io", severity="error", message=str(exc)))
            continue
        except ParserError as exc:
            findings.append(_finding(record=record, code="localization_parse_error", category="parser", severity="error", message=str(exc)))
            continue
        entries = {entry.key: entry for entry in parsed.entries}
        missing = source_keys - set(entries)
        extra = set(entries) - source_keys
        for key in sorted(missing):
            findings.append(_key_finding(record, key, "missing_key", "coverage", "error", "target is missing key"))
        for key in sorted(extra):
            findings.append(_key_finding(record, key, "extra_key", "coverage", "warning", "target has key not present in authoritative source"))
        if record["role"] == "target":
            for key in sorted(source_keys & set(entries)):
                source = source_entries[key]
                target = entries[key]
                if source.placeholder_signature != target.placeholder_signature:
                    findings.append(_key_finding(record, key, "placeholder_mismatch", "placeholder_integrity", "error", "target placeholder signature differs from source"))
                _append_mojibake_finding(findings, fixes, record, key, target.value, path, record["format"])
                if profile == "release":
                    if _source_equal_target(key, source.value, target.value):
                        findings.append(_key_finding(record, key, "source_equal_target", "translation_quality", "warning", "target equals source for a translatable key"))
                    if source.value.count("\n") != target.value.count("\n"):
                        findings.append(_key_finding(record, key, "newline_count_changed", "layout", "warning", "target newline count differs from source"))
        else:
            for key, entry in sorted(entries.items()):
                _append_mojibake_finding(findings, fixes, record, key, entry.value, path, record["format"])
    return findings, fixes, scanned


def _audit_translation_memory(root: Path, manifest: dict, project_id: str) -> tuple[list[dict], list[Fix], int]:
    tm_path = root / manifest["artifacts"]["translation_memory"]
    if not tm_path.exists():
        return [], [], 0
    findings: list[dict] = []
    fixes: list[Fix] = []
    scanned = 0
    with sqlite3.connect(tm_path) as conn:
        rows = conn.execute(
            """
            SELECT target_locale, key, target_value
            FROM memory_entries
            WHERE project_id = ? AND is_current = 1
            ORDER BY target_locale, key
            """,
            (project_id,),
        ).fetchall()
    for target_locale, key, target_value in rows:
        scanned += 1
        record = {
            "locale": target_locale,
            "path": manifest["artifacts"]["translation_memory"],
            "localization_id": f"tm::{target_locale}",
        }
        _append_mojibake_finding(findings, fixes, record, key, target_value, tm_path, "translation_memory")
    return findings, fixes, scanned


def _append_mojibake_finding(
    findings: list[dict],
    fixes: list[Fix],
    record: dict,
    key: str,
    value: str,
    path: Path,
    fmt: str,
) -> None:
    if not _has_mojibake(value):
        return
    suggested = _repair_mojibake(value)
    finding = _key_finding(record, key, "mojibake_suspected", "encoding", "warning", "value contains likely mojibake or replacement characters")
    finding["value_preview"] = _preview(value)
    if suggested and suggested != value:
        finding["suggested_value"] = suggested
        finding["fixable"] = True
        fixes.append(
            Fix(
                path=path,
                rel_path=str(record["path"]),
                locale=str(record["locale"]),
                localization_id=str(record["localization_id"]),
                key=key,
                old_value=value,
                new_value=suggested,
                fmt=fmt,
            )
        )
    else:
        finding["fixable"] = False
    findings.append(finding)


def _fixed_files(fixes: list[Fix]) -> dict[Path, bytes]:
    by_path: dict[Path, list[Fix]] = {}
    for fix in fixes:
        if fix.fmt == "translation_memory":
            continue
        by_path.setdefault(fix.path, []).append(fix)
    files: dict[Path, bytes] = {}
    for path, path_fixes in by_path.items():
        content = path.read_text(encoding="utf-8")
        for fix in path_fixes:
            content = _replace_value(content, fix)
        files[path] = content.encode("utf-8")
    return files


def _replace_value(content: str, fix: Fix) -> str:
    if fix.fmt == "ios_strings":
        old = _encode_ios_string(fix.old_value)
        new = _encode_ios_string(fix.new_value)
        pattern = re.compile(rf'("{re.escape(_encode_ios_string(fix.key))}"\s*=\s*)"{re.escape(old)}"(\s*;)')
        replaced, count = pattern.subn(rf'\1"{new}"\2', content, count=1)
        if count != 1:
            raise ParserError(f"unable to apply lint fix for key: {fix.key}")
        return replaced
    if fix.fmt == "android_xml":
        old = _encode_xml_text(fix.old_value)
        new = _encode_xml_text(fix.new_value)
        replaced = content.replace(f">{old}</string>", f">{new}</string>", 1)
        if replaced == content:
            raise ParserError(f"unable to apply lint fix for key: {fix.key}")
        return replaced
    return content


def _tm_bytes_after_fixes(tm_path: Path, fixes: list[Fix]) -> bytes:
    with tempfile.NamedTemporaryFile(prefix="parley-lint-tm-", suffix=".sqlite", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        shutil.copy2(tm_path, temp_path)
        with sqlite3.connect(temp_path) as conn:
            for fix in fixes:
                conn.execute(
                    """
                    UPDATE memory_entries
                    SET target_value = ?
                    WHERE target_locale = ? AND key = ? AND is_current = 1 AND target_value = ?
                    """,
                    (fix.new_value, fix.locale, fix.key, fix.old_value),
                )
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def _source_entries(canonical: dict) -> dict[str, ParsedEntry]:
    entries = {}
    for key, item in canonical["entries"].items():
        entries[key] = ParsedEntry(key=key, value=item["authoritative_value"], placeholders=item.get("placeholders", []))
    return entries


def _source_equal_target(key: str, source_value: str, target_value: str) -> bool:
    if key in SOURCE_EQUAL_ALLOWLIST:
        return False
    if source_value != target_value:
        return False
    if source_value.startswith(("http://", "https://")):
        return False
    if re.search(r"\.(txt|pdf|html?)$", source_value, re.IGNORECASE):
        return False
    return bool(re.search(r"[A-Za-z]{3,}", source_value))


def _has_mojibake(value: str) -> bool:
    return any(pattern in value for pattern in MOJIBAKE_PATTERNS)


def _repair_mojibake(value: str) -> str | None:
    best = value
    best_score = _mojibake_score(value)
    current = value
    for _ in range(3):
        try:
            candidate = current.encode("latin-1").decode("utf-8")
        except UnicodeError:
            break
        score = _mojibake_score(candidate)
        if score > best_score:
            break
        current = candidate
        if score < best_score:
            best = candidate
            best_score = score
        if score == 0:
            break
    return best if best != value and best_score < _mojibake_score(value) else None


def _mojibake_score(value: str) -> int:
    return sum(value.count(pattern) for pattern in MOJIBAKE_PATTERNS) + sum(1 for char in value if 0x80 <= ord(char) <= 0x9F)


def _key_finding(record: dict, key: str, code: str, category: str, severity: str, message: str) -> dict:
    finding = _finding(record=record, code=code, category=category, severity=severity, message=message)
    finding["key"] = key
    finding["stable_id"] = "|".join([str(record["path"]), code, key])
    return finding


def _finding(*, record: dict, code: str, category: str, severity: str, message: str) -> dict:
    return {
        "stable_id": "|".join([str(record["path"]), code]),
        "severity": severity,
        "category": category,
        "failure_category": category,
        "locale": record.get("locale"),
        "path": record.get("path"),
        "localization_id": record.get("localization_id"),
        "code": code,
        "message": message,
    }


def fix_to_payload(fix: Fix) -> dict:
    return {
        "path": fix.rel_path,
        "locale": fix.locale,
        "localization_id": fix.localization_id,
        "key": fix.key,
        "old_value": fix.old_value,
        "new_value": fix.new_value,
    }


def _preview(value: str) -> str:
    return " ".join(value.split())[:160]


def _encode_ios_string(value: str) -> str:
    replacements = {
        "\\": "\\\\",
        '"': '\\"',
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\f": "\\f",
        "\v": "\\v",
        "\u0085": "\\u0085",
        "\u2028": "\\u2028",
        "\u2029": "\\u2029",
    }
    return "".join(replacements.get(char, char) for char in value)


def _encode_xml_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
