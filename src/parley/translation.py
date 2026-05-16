from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_IO_OR_PARSER, EXIT_OK, EXIT_PROVIDER, EXIT_USAGE_OR_SCHEMA, FileIOError, ParleyError, UsageError
from parley.parsers import ParsedEntry, parse_localization, serialize_localization
from parley.paths import canonical_relative_path, resolve_report_dir
from parley.providers import TranslationRequest, translation_provider
from parley.reports import prepare_report, utc_now
from parley.validation import CommandResult


@dataclass(frozen=True)
class TranslationRecord:
    tm_record_id: str
    target_value: str
    source_content_hash: str
    last_translated_source_hash: str
    placeholder_signature: str
    provenance: str
    human_status: str
    is_current: bool
    updated_at: str


def translate_project(
    *,
    project_root: str | None,
    target_locale: str,
    target_path: str | None,
    reuse_mode: str,
    provider: str,
    dry_run: bool,
    no_provider: bool,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifact_issues = schema_issues_for_required(
            root,
            [
                "parley.yaml",
                "inventory.yaml",
                "canonical-inventory.json",
                "translation-memory.sqlite",
                "context-anchor.yaml",
            ],
        )
        if artifact_issues:
            message = "; ".join(issue.message for issue in artifact_issues)
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], message)
        artifacts = load_project_artifacts(root, include_canonical=True)
        assert artifacts.canonical_inventory is not None
        canonical = artifacts.canonical_inventory
        _ensure_populated_context_anchor(artifacts.context_anchor, canonical)
        authoritative = _authoritative_record(artifacts.inventory, artifacts.manifest)
        normalized_target_locale = _lower_ascii(target_locale)
        target = _target_record(
            root=root,
            inventory=artifacts.inventory,
            target_locale=normalized_target_locale,
            target_path=target_path,
            cwd=cwd,
        )
        report_root = resolve_report_dir(root, report_dir)
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))

    try:
        source_content = (root / authoritative["path"]).read_text(encoding="utf-8")
        source_parsed = parse_localization(source_content, authoritative["format"])
    except OSError as exc:
        return _write_translation_report(
            root=root,
            report_root=report_root,
            started_at=started_at,
            project_id=artifacts.project_id,
            target=target,
            target_locale=normalized_target_locale,
            reuse_mode=reuse_mode,
            exit_code=EXIT_IO_OR_PARSER,
            provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
            per_key_outcomes=[],
            failure_category="source_io_error",
            dry_run=dry_run,
            no_provider=no_provider,
            provider=provider,
            message=str(exc),
        )
    except ParleyError as exc:
        return _write_translation_report(
            root=root,
            report_root=report_root,
            started_at=started_at,
            project_id=artifacts.project_id,
            target=target,
            target_locale=normalized_target_locale,
            reuse_mode=reuse_mode,
            exit_code=EXIT_IO_OR_PARSER,
            provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
            per_key_outcomes=[],
            failure_category="source_parse_error",
            dry_run=dry_run,
            no_provider=no_provider,
            provider=provider,
            message=str(exc),
        )

    target_entries: dict[str, ParsedEntry] = {}
    target_file = root / target["path"]
    if target_file.exists():
        try:
            target_content = target_file.read_text(encoding="utf-8")
            target_parsed = parse_localization(target_content, target["format"])
            target_entries = {entry.key: entry for entry in target_parsed.entries}
        except OSError as exc:
            return _write_translation_report(
                root=root,
                report_root=report_root,
                started_at=started_at,
                project_id=artifacts.project_id,
                target=target,
                target_locale=normalized_target_locale,
                reuse_mode=reuse_mode,
                exit_code=EXIT_IO_OR_PARSER,
                provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
                per_key_outcomes=[],
                failure_category="target_io_error",
                dry_run=dry_run,
                no_provider=no_provider,
                provider=provider,
                message=str(exc),
            )
        except ParleyError as exc:
            return _write_translation_report(
                root=root,
                report_root=report_root,
                started_at=started_at,
                project_id=artifacts.project_id,
                target=target,
                target_locale=normalized_target_locale,
                reuse_mode=reuse_mode,
                exit_code=EXIT_IO_OR_PARSER,
                provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
                per_key_outcomes=[],
                failure_category="target_parse_error",
                dry_run=dry_run,
                no_provider=no_provider,
                provider=provider,
                message=str(exc),
            )

    source_entries = {entry.key: entry for entry in source_parsed.entries}
    canonical_keys = sorted(canonical["entries"])
    missing_source = [key for key in canonical_keys if key not in source_entries]
    if missing_source:
        outcomes = [
            _outcome(key, "failed", "source_missing" if key in missing_source else "not_attempted")
            for key in canonical_keys
        ]
        return _write_translation_report(
            root=root,
            report_root=report_root,
            started_at=started_at,
            project_id=artifacts.project_id,
            target=target,
            target_locale=normalized_target_locale,
            reuse_mode=reuse_mode,
            exit_code=EXIT_USAGE_OR_SCHEMA,
            provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
            per_key_outcomes=outcomes,
            failure_category="source_missing",
            dry_run=dry_run,
            no_provider=no_provider,
            provider=provider,
        )

    try:
        with sqlite3.connect(root / artifacts.manifest["artifacts"]["translation_memory"]) as conn:
            outcomes = _evaluate_outcomes(
                conn=conn,
                project_id=artifacts.project_id,
                canonical=canonical,
                source_locale=artifacts.manifest["project"]["authoritative_locale"],
                target_locale=normalized_target_locale,
                target_entries=target_entries,
                reuse_mode=reuse_mode,
            )
    except TranslationMemoryConflict as exc:
        outcomes = [
            _outcome(key, "failed", "tm_current_conflict" if key == exc.key else "not_attempted")
            for key in canonical_keys
        ]
        return _write_translation_report(
            root=root,
            report_root=report_root,
            started_at=started_at,
            project_id=artifacts.project_id,
            target=target,
            target_locale=normalized_target_locale,
            reuse_mode=reuse_mode,
            exit_code=EXIT_USAGE_OR_SCHEMA,
            provider_status="not_applicable" if reuse_mode == "tm_only" else "skipped",
            per_key_outcomes=outcomes,
            failure_category="tm_current_conflict",
            dry_run=dry_run,
            no_provider=no_provider,
            provider=provider,
        )
    except sqlite3.DatabaseError as exc:
        return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"invalid translation-memory.sqlite: {exc}")

    provider_required = any(item["outcome"] == "generated" for item in outcomes)
    provider_status = "not_applicable" if reuse_mode == "tm_only" else "skipped"
    provider_skip_reason = None if reuse_mode == "tm_only" else "not_needed"
    provider_failure_category = None
    if provider_required:
        if no_provider:
            outcomes = [
                _replace_generated(item, "provider_disallowed")
                for item in outcomes
            ]
            exit_code = EXIT_USAGE_OR_SCHEMA
            failure_category = "provider_disallowed"
            provider_status = "skipped"
            provider_skip_reason = "no_provider"
        else:
            try:
                provider_client = translation_provider(provider)
                outcomes = _generate_outcomes(
                    provider_client=provider_client,
                    outcomes=outcomes,
                    canonical=canonical,
                    source_locale=artifacts.manifest["project"]["authoritative_locale"],
                    target_locale=normalized_target_locale,
                )
                exit_code = EXIT_OK
                failure_category = None
                provider_status = "used"
                provider_skip_reason = None
            except Exception:
                outcomes = _mark_provider_unavailable(outcomes)
                exit_code = EXIT_PROVIDER
                failure_category = "provider_failed"
                provider_status = "failed"
                provider_skip_reason = None
                provider_failure_category = "unavailable"
    elif any(item["outcome"] == "failed" for item in outcomes):
        exit_code = EXIT_BLOCKING_FINDINGS
        failure_category = None
    else:
        exit_code = EXIT_OK
        failure_category = None

    validation_findings: list[dict] = []
    files: dict[Path, bytes] = {}
    if exit_code == EXIT_OK:
        staged_entries = _staged_target_entries(canonical_keys, target_entries, outcomes)
        staged_content = serialize_localization(staged_entries, target["format"])
        staged_parsed = parse_localization(staged_content, target["format"])
        validation_findings = _placeholder_findings(target, staged_parsed.entries, canonical)
        if validation_findings:
            exit_code = EXIT_BLOCKING_FINDINGS
            failure_category = "blocking_validation_findings"
        elif not dry_run:
            files[target_file] = staged_content.encode("utf-8")

    return _write_translation_report(
        root=root,
        report_root=report_root,
        started_at=started_at,
        project_id=artifacts.project_id,
        target=target,
        target_locale=normalized_target_locale,
        reuse_mode=reuse_mode,
        exit_code=exit_code,
        provider_status=provider_status,
        per_key_outcomes=outcomes,
        failure_category=failure_category,
        dry_run=dry_run,
        no_provider=no_provider,
        provider=provider,
        files=files,
        provider_skip_reason=provider_skip_reason,
        provider_failure_category=provider_failure_category,
        validation_findings=validation_findings,
    )


class TranslationMemoryConflict(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _evaluate_outcomes(
    *,
    conn: sqlite3.Connection,
    project_id: str,
    canonical: dict,
    source_locale: str,
    target_locale: str,
    target_entries: dict[str, ParsedEntry],
    reuse_mode: str,
) -> list[dict]:
    outcomes: list[dict] = []
    for key in sorted(canonical["entries"]):
        canonical_entry = canonical["entries"][key]
        current_records = _current_records(conn, project_id, key, source_locale, target_locale)
        if len(current_records) > 1:
            raise TranslationMemoryConflict(key)
        current = current_records[0] if current_records else None
        existing = target_entries.get(key)
        existing_value = existing.value if existing else None
        if (
            current
            and current.last_translated_source_hash == canonical_entry["content_hash"]
            and current.target_value == existing_value
        ):
            outcomes.append(_outcome(key, "skipped", "unchanged", current.tm_record_id))
            continue
        if current and current.human_status in {"approved", "locked"} and current.target_value == existing_value:
            outcomes.append(_outcome(key, "skipped", "human_status_preserved", current.tm_record_id))
            continue
        if current and current.human_status in {"approved", "locked"}:
            outcomes.append(_outcome(key, "failed", "target_tm_conflict", current.tm_record_id))
            continue
        if reuse_mode in {"tm_only", "tm_then_provider"}:
            winner = _reuse_winner(
                conn,
                project_id,
                key,
                source_locale,
                target_locale,
                canonical_entry["placeholder_signature"],
            )
            if winner:
                outcomes.append(_outcome(key, "reused", tm_record_id=winner.tm_record_id, target_value=winner.target_value))
                continue
        if reuse_mode in {"tm_then_provider", "provider_only"}:
            outcomes.append(_outcome(key, "generated"))
            continue
        outcomes.append(_outcome(key, "failed", "tm_miss"))
    return outcomes


def _current_records(conn: sqlite3.Connection, project_id: str, key: str, source_locale: str, target_locale: str) -> list[TranslationRecord]:
    return [
        _record(row)
        for row in conn.execute(
            """
            SELECT tm_record_id, target_value, source_content_hash, last_translated_source_hash,
                   placeholder_signature, provenance, human_status, is_current, updated_at
            FROM memory_entries
            WHERE project_id = ? AND key = ? AND source_locale = ? AND target_locale = ? AND is_current = 1
            ORDER BY tm_record_id
            """,
            (project_id, key, source_locale, target_locale),
        )
    ]


def _reuse_winner(
    conn: sqlite3.Connection,
    project_id: str,
    key: str,
    source_locale: str,
    target_locale: str,
    placeholder_signature: str,
) -> TranslationRecord | None:
    records = [
        _record(row)
        for row in conn.execute(
            """
            SELECT tm_record_id, target_value, source_content_hash, last_translated_source_hash,
                   placeholder_signature, provenance, human_status, is_current, updated_at
            FROM memory_entries
            WHERE project_id = ? AND key = ? AND source_locale = ? AND target_locale = ?
              AND placeholder_signature = ?
            """,
            (project_id, key, source_locale, target_locale, placeholder_signature),
        )
    ]
    if not records:
        return None
    return sorted(records, key=_reuse_sort_key)[0]


def _record(row) -> TranslationRecord:
    return TranslationRecord(
        tm_record_id=str(row[0]),
        target_value=str(row[1]),
        source_content_hash=str(row[2]),
        last_translated_source_hash=str(row[3]),
        placeholder_signature=str(row[4]),
        provenance=str(row[5]),
        human_status=str(row[6]),
        is_current=bool(row[7]),
        updated_at=str(row[8]),
    )


def _reuse_sort_key(record: TranslationRecord) -> tuple:
    human_rank = {"approved": 0, "locked": 0, "reviewed": 1, "draft": 2}
    provenance_rank = {"human_approved": 0, "human_reviewed": 1, "machine_generated": 2, "imported": 3}
    return (
        human_rank.get(record.human_status, 9),
        provenance_rank.get(record.provenance, 9),
        _reverse_lexical(record.updated_at),
        record.tm_record_id,
    )


def _reverse_lexical(value: str) -> tuple[int, ...]:
    return tuple(-ord(ch) for ch in value)


def _write_translation_report(
    *,
    root: Path,
    report_root: Path,
    started_at: str,
    project_id: str,
    target: dict,
    target_locale: str,
    reuse_mode: str,
    exit_code: int,
    provider_status: str,
    per_key_outcomes: list[dict],
    failure_category: str | None,
    dry_run: bool,
    no_provider: bool,
    provider: str,
    files: dict[Path, bytes] | None = None,
    provider_skip_reason: str | None = None,
    provider_failure_category: str | None = None,
    validation_findings: list[dict] | None = None,
    message: str | None = None,
) -> CommandResult:
    extra_fields = {
        "target_locale": target_locale,
        "target_path": target["path"],
        "reuse_mode": reuse_mode,
        "provider_status": provider_status,
        "per_key_outcomes": per_key_outcomes,
    }
    if provider_skip_reason:
        extra_fields["provider_skip_reason"] = provider_skip_reason
    if provider_failure_category:
        extra_fields["provider_failure_category"] = provider_failure_category
    if validation_findings is not None:
        extra_fields["validation_findings"] = validation_findings
    report = prepare_report(
        project_root=root,
        report_dir=report_root,
        family="translation",
        canonical_command="translate",
        project_id=project_id,
        started_at=started_at,
        exit_code=exit_code,
        inputs={
            "target_locale": target_locale,
            "target_path": target["path"],
            "reuse_mode": reuse_mode,
            "dry_run": dry_run,
            "no_provider": no_provider,
            "provider": provider,
        },
        summary={
            "key_count": len(per_key_outcomes),
            "failed_count": sum(1 for item in per_key_outcomes if item["outcome"] == "failed"),
            "reused_count": sum(1 for item in per_key_outcomes if item["outcome"] == "reused"),
            "skipped_count": sum(1 for item in per_key_outcomes if item["outcome"] == "skipped"),
            "generated_count": sum(1 for item in per_key_outcomes if item["outcome"] == "generated"),
        },
        failure_category=failure_category,
        extra_fields=extra_fields,
    )
    try:
        commit_files(root, files or {}, {report.path: report.content})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))
    return CommandResult(exit_code, [report.path], message)


def _authoritative_record(inventory: dict, manifest: dict) -> dict:
    expected_id = manifest["project"]["authoritative_localization_id"]
    matches = [
        record
        for record in inventory["localizations"]
        if record["localization_id"] == expected_id and record["role"] == "authoritative"
    ]
    if len(matches) != 1:
        raise UsageError("unable to resolve authoritative localization", failure_category="artifact_schema")
    return matches[0]


def _target_record(*, root: Path, inventory: dict, target_locale: str, target_path: str | None, cwd: Path) -> dict:
    candidates = [
        record
        for record in inventory["localizations"]
        if record.get("role") == "target" and record.get("locale") == target_locale
    ]
    if target_path:
        rel_target_path = canonical_relative_path(root, target_path, cwd.absolute())
        candidates = [record for record in candidates if record.get("path") == rel_target_path]
    if len(candidates) != 1:
        raise UsageError("unable to resolve exactly one target localization")
    return candidates[0]


def _ensure_populated_context_anchor(context_anchor: dict | None, canonical: dict) -> None:
    if not context_anchor:
        raise UsageError("context-anchor.yaml is missing or empty", failure_category="artifact_schema")
    entries = context_anchor.get("entries")
    if not isinstance(entries, dict):
        raise UsageError("context-anchor.yaml entries are invalid", failure_category="artifact_schema")
    for key in sorted(canonical["entries"]):
        value = entries.get(key)
        if isinstance(value, dict):
            value = value.get("context") or value.get("description")
        if not isinstance(value, str) or not value.strip():
            raise UsageError("context-anchor.yaml lacks populated per-key context", failure_category="artifact_schema")


def _outcome(
    key: str,
    outcome: str,
    category: str | None = None,
    tm_record_id: str | None = None,
    target_value: str | None = None,
) -> dict:
    item = {"key": key, "outcome": outcome}
    if category:
        item["category"] = category
    if tm_record_id:
        item["tm_record_id"] = tm_record_id
    if target_value is not None:
        item["target_value"] = target_value
    return item


def _replace_generated(item: dict, category: str) -> dict:
    if item["outcome"] != "generated":
        return item
    return _outcome(item["key"], "failed", category)


def _mark_provider_unavailable(outcomes: list[dict]) -> list[dict]:
    marked: list[dict] = []
    failed_once = False
    for item in outcomes:
        if item["outcome"] != "generated":
            marked.append(item)
            continue
        if failed_once:
            marked.append(_outcome(item["key"], "failed", "provider_not_attempted_after_failure"))
        else:
            marked.append(_outcome(item["key"], "failed", "provider_failed"))
            failed_once = True
    return marked


def _generate_outcomes(
    *,
    provider_client,
    outcomes: list[dict],
    canonical: dict,
    source_locale: str,
    target_locale: str,
) -> list[dict]:
    generated: list[dict] = []
    for item in outcomes:
        if item["outcome"] != "generated":
            generated.append(item)
            continue
        canonical_entry = canonical["entries"][item["key"]]
        response = provider_client.translate(
            TranslationRequest(
                key=item["key"],
                source_value=canonical_entry["authoritative_value"],
                source_locale=source_locale,
                target_locale=target_locale,
                placeholder_signature=canonical_entry["placeholder_signature"],
            )
        )
        generated.append(
            _outcome(
                item["key"],
                "generated",
                tm_record_id=item.get("tm_record_id"),
                target_value=response.target_value,
            )
        )
    return generated


def _staged_target_entries(
    canonical_keys: list[str],
    target_entries: dict[str, ParsedEntry],
    outcomes: list[dict],
) -> list[ParsedEntry]:
    output = []
    outcome_by_key = {item["key"]: item for item in outcomes}
    for key in canonical_keys:
        outcome = outcome_by_key[key]
        if outcome["outcome"] in {"reused", "generated"}:
            value = outcome["target_value"]
        else:
            value = target_entries[key].value
        output.append(ParsedEntry(key=key, value=value, placeholders=[]))
    return output


def _placeholder_findings(target: dict, entries: list[ParsedEntry], canonical: dict) -> list[dict]:
    findings = []
    by_key = {entry.key: entry for entry in entries}
    for key in sorted(canonical["entries"]):
        actual = by_key[key].placeholder_signature
        expected = canonical["entries"][key].get("placeholder_signature", "")
        if actual != expected:
            findings.append(
                {
                    "stable_id": "|".join([target["path"], "placeholder_mismatch", key]),
                    "severity": "blocking",
                    "category": "placeholder_integrity",
                    "failure_category": "placeholder_mismatch",
                    "path": target["path"],
                    "locale": target["locale"],
                    "localization_id": target["localization_id"],
                    "key": key,
                    "code": "placeholder_mismatch",
                    "message": f"placeholder mismatch for key: {key}",
                }
            )
    return findings


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
