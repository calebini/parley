from __future__ import annotations

from pathlib import Path
import sqlite3

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_IO_OR_PARSER, EXIT_OK, EXIT_USAGE_OR_SCHEMA, ParleyError, UsageError
from parley.hashing import sha256_canonical_json
from parley.parsers import parse_localization
from parley.paths import canonical_localization_path, localization_file_path, resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.validation import CommandResult


def import_target_to_memory(
    *,
    project_root: str | None,
    target_locale: str,
    target_path: str | None,
    status: str,
    dry_run: bool,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifact_issues = schema_issues_for_required(
            root,
            ["parley.yaml", "inventory.yaml", "canonical-inventory.json", "translation-memory.sqlite"],
        )
        if artifact_issues:
            message = "; ".join(issue.message for issue in artifact_issues)
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], message)
        artifacts = load_project_artifacts(root, include_canonical=True, include_context=False)
        assert artifacts.canonical_inventory is not None
        canonical = artifacts.canonical_inventory
        normalized_target_locale = _lower_ascii(target_locale)
        target = _target_record(
            manifest=artifacts.manifest,
            inventory=artifacts.inventory,
            target_locale=normalized_target_locale,
            target_path=target_path,
            root=root,
            cwd=cwd,
        )
        target_file = localization_file_path(root, artifacts.manifest, target["path"])
        content = target_file.read_text(encoding="utf-8")
        parsed = parse_localization(content, target["format"])
    except FileNotFoundError as exc:
        return CommandResult(EXIT_IO_OR_PARSER, [], str(exc))
    except OSError as exc:
        return CommandResult(EXIT_IO_OR_PARSER, [], str(exc))
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))

    parsed_by_key = {entry.key: entry for entry in parsed.entries}
    findings: list[dict] = []
    imported_entries: list[dict] = []
    for key in sorted(canonical["entries"]):
        canonical_entry = canonical["entries"][key]
        target_entry = parsed_by_key.get(key)
        if target_entry is None:
            findings.append(_finding(target, key, "missing_key", "missing target key; not imported"))
            continue
        expected = canonical_entry.get("placeholder_signature", "")
        actual = target_entry.placeholder_signature
        if actual != expected:
            findings.append(_finding(target, key, "placeholder_mismatch", "placeholder mismatch; not imported"))
            continue
        imported_entries.append(
            {
                "key": key,
                "tm_record_id": _imported_tm_record_id(
                    project_id=artifacts.project_id,
                    key=key,
                    source_locale=canonical["authoritative_locale"],
                    target_locale=normalized_target_locale,
                    source_content_hash=canonical_entry["content_hash"],
                    target_value=target_entry.value,
                    placeholder_signature=expected,
                ),
                "target_value": target_entry.value,
                "source_content_hash": canonical_entry["content_hash"],
                "placeholder_signature": expected,
            }
        )

    for key in sorted(set(parsed_by_key) - set(canonical["entries"])):
        findings.append(_finding(target, key, "extra_key", "extra target key; not imported"))

    exit_code = EXIT_BLOCKING_FINDINGS if findings else EXIT_OK
    files: dict[Path, bytes] = {}
    tm_written = False
    if imported_entries and not dry_run:
        try:
            files[root / artifacts.manifest["artifacts"]["translation_memory"]] = _memory_after_import(
                tm_path=root / artifacts.manifest["artifacts"]["translation_memory"],
                project_id=artifacts.project_id,
                source_locale=canonical["authoritative_locale"],
                target_locale=normalized_target_locale,
                entries=imported_entries,
                human_status=status,
                updated_at=started_at,
            )
            tm_written = True
        except sqlite3.DatabaseError as exc:
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"invalid translation-memory.sqlite: {exc}")

    report = prepare_report(
        project_root=root,
        report_dir=resolve_report_dir(root, report_dir),
        family="translation_memory",
        canonical_command="tm_import_target",
        project_id=artifacts.project_id,
        started_at=started_at,
        exit_code=exit_code,
        inputs={
            "target_locale": normalized_target_locale,
            "target_path": target["path"],
            "status": status,
            "dry_run": dry_run,
        },
        summary={
            "canonical_key_count": len(canonical["entries"]),
            "imported_count": len(imported_entries),
            "finding_count": len(findings),
            "tm_written": tm_written,
            "dry_run": dry_run,
        },
        findings=findings,
        failure_category="blocking_validation" if findings else None,
        extra_fields={
            "target_locale": normalized_target_locale,
            "target_path": target["path"],
            "imported_entries": [
                {"key": entry["key"], "tm_record_id": entry["tm_record_id"]}
                for entry in imported_entries
            ],
        },
    )
    try:
        commit_files(root, files, {report.path: report.content})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))
    return CommandResult(exit_code, [report.path])


def _target_record(*, manifest: dict, inventory: dict, target_locale: str, target_path: str | None, root: Path, cwd: Path) -> dict:
    candidates = [
        record
        for record in inventory["localizations"]
        if record.get("role") == "target" and record.get("locale") == target_locale
    ]
    if target_path:
        rel_target_path = canonical_localization_path(root, manifest, target_path, cwd.absolute())
        candidates = [record for record in candidates if record.get("path") == rel_target_path]
    if len(candidates) != 1:
        raise UsageError("unable to resolve exactly one target localization")
    return candidates[0]


def _memory_after_import(
    *,
    tm_path: Path,
    project_id: str,
    source_locale: str,
    target_locale: str,
    entries: list[dict],
    human_status: str,
    updated_at: str,
) -> bytes:
    original = tm_path.read_bytes()
    conn = sqlite3.connect(":memory:")
    try:
        conn.deserialize(original)
        _ensure_memory_columns(conn)
        for entry in entries:
            _write_imported_record(
                conn=conn,
                project_id=project_id,
                source_locale=source_locale,
                target_locale=target_locale,
                key=entry["key"],
                source_content_hash=entry["source_content_hash"],
                target_value=entry["target_value"],
                placeholder_signature=entry["placeholder_signature"],
                tm_record_id=entry["tm_record_id"],
                human_status=human_status,
                updated_at=updated_at,
            )
        conn.commit()
        return conn.serialize()
    finally:
        conn.close()


def _ensure_memory_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_entries)")}
    additions = {
        "confidence_json": "ALTER TABLE memory_entries ADD COLUMN confidence_json TEXT NOT NULL DEFAULT '{}'",
        "metadata_json": "ALTER TABLE memory_entries ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'",
        "created_at": "ALTER TABLE memory_entries ADD COLUMN created_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00.000000Z'",
    }
    for column, statement in additions.items():
        if column not in columns:
            conn.execute(statement)


def _write_imported_record(
    *,
    conn: sqlite3.Connection,
    project_id: str,
    source_locale: str,
    target_locale: str,
    key: str,
    source_content_hash: str,
    target_value: str,
    placeholder_signature: str,
    tm_record_id: str,
    human_status: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        UPDATE memory_entries
        SET is_current = 0
        WHERE project_id = ? AND key = ? AND source_locale = ? AND target_locale = ?
          AND tm_record_id != ?
        """,
        (project_id, key, source_locale, target_locale, tm_record_id),
    )
    conn.execute(
        """
        INSERT INTO memory_entries (
            tm_record_id, project_id, key, source_locale, target_locale,
            source_content_hash, last_translated_source_hash, target_value,
            placeholder_signature, provenance, human_status, is_current,
            confidence_json, metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'imported', ?, 1, '{}', '{}', ?, ?)
        ON CONFLICT(tm_record_id) DO UPDATE SET
            source_content_hash = excluded.source_content_hash,
            last_translated_source_hash = excluded.last_translated_source_hash,
            target_value = excluded.target_value,
            placeholder_signature = excluded.placeholder_signature,
            provenance = 'imported',
            human_status = excluded.human_status,
            is_current = 1,
            updated_at = excluded.updated_at
        """,
        (
            tm_record_id,
            project_id,
            key,
            source_locale,
            target_locale,
            source_content_hash,
            source_content_hash,
            target_value,
            placeholder_signature,
            human_status,
            updated_at,
            updated_at,
        ),
    )


def _imported_tm_record_id(
    *,
    project_id: str,
    key: str,
    source_locale: str,
    target_locale: str,
    source_content_hash: str,
    target_value: str,
    placeholder_signature: str,
) -> str:
    digest = sha256_canonical_json(
        {
            "provenance": "imported",
            "project_id": project_id,
            "key": key,
            "source_locale": source_locale,
            "target_locale": target_locale,
            "source_content_hash": source_content_hash,
            "target_value": target_value,
            "placeholder_signature": placeholder_signature,
        }
    )
    return f"tm-{digest[:32]}"


def _finding(target: dict, key: str, code: str, message: str) -> dict:
    return {
        "stable_id": "|".join([target["path"], code, key]),
        "severity": "blocking",
        "category": "translation_memory_import",
        "failure_category": code,
        "path": target["path"],
        "locale": target["locale"],
        "localization_id": target["localization_id"],
        "key": key,
        "code": code,
        "message": message,
    }


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
