from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from parley.errors import EXIT_OK, FileIOError, ParleyError, UsageError
from parley.hashing import sha256_canonical_json, sha256_text
from parley.parsers import infer_format, parse_localization
from parley.paths import canonical_relative_path, resolve_report_dir
from parley.reports import PreparedReport, ensure_report_can_be_written, prepare_report, utc_now
from parley.serialization import pretty_json, yaml_dump


MANAGED_INIT_PATHS = [
    "parley.yaml",
    "inventory.yaml",
    "canonical-inventory.json",
    "context-anchor.yaml",
    "glossary.yaml",
    "translation-memory.sqlite",
    ".parley",
    "reports",
]

CORE_ARTIFACTS = [
    "parley.yaml",
    "inventory.yaml",
    "canonical-inventory.json",
    "context-anchor.yaml",
    "glossary.yaml",
    "translation-memory.sqlite",
]


@dataclass(frozen=True)
class InitResult:
    exit_code: int
    reports: list[Path]
    message: str | None = None


def project_init(
    *,
    project_root: Path,
    name: str,
    authoritative: str,
    locale: str,
    fmt: str | None,
    force: bool,
    report_dir: str | None,
    cwd: Path,
) -> InitResult:
    started_at = utc_now()
    try:
        prepared = _prepare_init(
            project_root=project_root,
            name=name,
            authoritative=authoritative,
            locale=locale,
            fmt=fmt,
            force=force,
            report_dir=report_dir,
            cwd=cwd,
            started_at=started_at,
        )
        _commit_prepared(project_root=project_root, prepared=prepared, force=force)
        return InitResult(EXIT_OK, [prepared.report.path])
    except ParleyError as exc:
        return InitResult(exc.exit_code, [], str(exc))


@dataclass(frozen=True)
class PreparedInit:
    files: dict[str, bytes]
    report: PreparedReport


def _prepare_init(
    *,
    project_root: Path,
    name: str,
    authoritative: str,
    locale: str,
    fmt: str | None,
    force: bool,
    report_dir: str | None,
    cwd: Path,
    started_at: str,
) -> PreparedInit:
    project_root = project_root.absolute()
    if not project_root.exists():
        project_root.mkdir(parents=True)
    if not project_root.is_dir():
        raise UsageError("--project-root must be a directory")
    if not force:
        existing = [rel for rel in MANAGED_INIT_PATHS if (project_root / rel).exists()]
        if existing:
            raise UsageError(f"project already contains Parley managed paths: {', '.join(existing)}")

    project_rel_path = canonical_relative_path(project_root, authoritative, cwd.absolute())
    authoritative_path = project_root / project_rel_path
    selected_format = fmt or infer_format(project_rel_path)
    if selected_format not in {"ios_strings", "android_xml"}:
        raise UsageError("unable to determine authoritative localization format")
    try:
        source_bytes = authoritative_path.read_bytes()
    except OSError as exc:
        raise FileIOError(f"unable to read authoritative localization: {authoritative_path}") from exc
    try:
        parsed = parse_localization(source_bytes.decode("utf-8"), selected_format)
    except UnicodeDecodeError as exc:
        raise FileIOError(f"authoritative localization is not UTF-8: {authoritative_path}") from exc

    normalized_locale = _lower_ascii(locale)
    project_id = _id_from_name(name)
    localization_id = f"{normalized_locale}::{project_rel_path}"
    generated_at = started_at
    canonical_entries = {}
    inventory_hash_input_entries = {}
    for entry in parsed.entries:
        content_input = {
            "key": entry.key,
            "value": entry.value,
            "locale": normalized_locale,
            "format": selected_format,
            "placeholder_signature": entry.placeholder_signature,
        }
        canonical_entries[entry.key] = {
            "key": entry.key,
            "authoritative_value": entry.value,
            "value_hash": sha256_text(entry.value),
            "content_hash": sha256_canonical_json(content_input),
            "placeholder_signature": entry.placeholder_signature,
            "placeholders": entry.placeholders,
            "first_seen_at": generated_at,
            "last_updated_at": generated_at,
        }
        inventory_hash_input_entries[entry.key] = {
            "authoritative_value": entry.value,
            "placeholder_signature": entry.placeholder_signature,
        }
    inventory_hash = sha256_canonical_json(
        {
            "authoritative_locale": normalized_locale,
            "authoritative_format": selected_format,
            "entries": inventory_hash_input_entries,
        }
    )
    parley_manifest = {
        "schema_version": "1.0",
        "project": {
            "id": project_id,
            "name": name,
            "authoritative_localization_id": localization_id,
            "authoritative_locale": normalized_locale,
        },
        "artifacts": {
            "inventory": "inventory.yaml",
            "canonical_inventory": "canonical-inventory.json",
            "context_anchor": "context-anchor.yaml",
            "glossary": "glossary.yaml",
            "translation_memory": "translation-memory.sqlite",
        },
        "defaults": {"report_format": "json"},
    }
    inventory = {
        "schema_version": "1.0",
        "project_id": project_id,
        "localizations": [
            {
                "localization_id": localization_id,
                "locale": normalized_locale,
                "format": selected_format,
                "path": project_rel_path,
                "role": "authoritative",
                "status": "draft",
                "parser": selected_format,
                "last_observed_hash": parsed.normalized_hash,
            }
        ],
    }
    canonical_inventory = {
        "schema_version": "1.0",
        "project_id": project_id,
        "authoritative_localization_id": localization_id,
        "authoritative_locale": normalized_locale,
        "authoritative_format": selected_format,
        "generated_at": generated_at,
        "inventory_hash": inventory_hash,
        "entries": canonical_entries,
    }
    context_anchor = {
        "schema_version": "1.0",
        "project_id": project_id,
        "authoritative_locale": normalized_locale,
        "project_context": {"description": ""},
        "entries": {},
    }
    glossary = {
        "schema_version": "1.0",
        "project_id": project_id,
        "glossary_version": "mvp",
        "rules": [],
    }
    report_root = resolve_report_dir(project_root, report_dir)
    report = prepare_report(
        project_root=project_root,
        report_dir=report_root,
        family="validation",
        canonical_command="project_init",
        project_id=project_id,
        started_at=started_at,
        exit_code=EXIT_OK,
        inputs={
            "project_root": str(project_root),
            "name": name,
            "authoritative": project_rel_path,
            "locale": normalized_locale,
            "format": selected_format,
            "force": force,
        },
        summary={
            "artifacts_created": len(CORE_ARTIFACTS),
            "canonical_entries": len(canonical_entries),
        },
    )
    ensure_report_can_be_written(report)
    sqlite_bytes = _empty_translation_memory_bytes()
    return PreparedInit(
        files={
            "parley.yaml": yaml_dump(parley_manifest).encode("utf-8"),
            "inventory.yaml": yaml_dump(inventory).encode("utf-8"),
            "canonical-inventory.json": pretty_json(canonical_inventory).encode("utf-8"),
            "context-anchor.yaml": yaml_dump(context_anchor).encode("utf-8"),
            "glossary.yaml": yaml_dump(glossary).encode("utf-8"),
            "translation-memory.sqlite": sqlite_bytes,
        },
        report=report,
    )


def _commit_prepared(*, project_root: Path, prepared: PreparedInit, force: bool) -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix=".parley-staging-", dir=project_root))
    backups: dict[Path, Path | None] = {}
    committed: list[Path] = []
    report_path = prepared.report.path
    try:
        staged_files: dict[str, Path] = {}
        for rel, content in prepared.files.items():
            staged = temp_dir / rel
            staged.write_bytes(content)
            staged_files[rel] = staged
        staged_report = temp_dir / "report.json"
        staged_report.write_text(prepared.report.content, encoding="utf-8")

        for rel in CORE_ARTIFACTS:
            final = project_root / rel
            backups[final] = _backup_path(final, temp_dir)
        backups[report_path] = _backup_path(report_path, temp_dir)

        for rel in CORE_ARTIFACTS:
            final = project_root / rel
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_files[rel], final)
            committed.append(final)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        if report_path.exists():
            raise FileIOError(f"report already exists: {report_path}")
        os.replace(staged_report, report_path)
        committed.append(report_path)
    except Exception as exc:
        _rollback(backups, committed)
        if isinstance(exc, ParleyError):
            raise
        raise FileIOError(f"failed to commit project artifacts: {exc}") from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _backup_path(path: Path, temp_dir: Path) -> Path | None:
    if not path.exists():
        return None
    backup = temp_dir / "backups" / sha256_text(str(path))
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def _rollback(backups: dict[Path, Path | None], committed: list[Path]) -> None:
    for path in reversed(committed):
        backup = backups.get(path)
        if backup is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, path)


def _empty_translation_memory_bytes() -> bytes:
    fd, path_str = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    path = Path(path_str)
    try:
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA user_version = 1")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    tm_record_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    source_locale TEXT NOT NULL,
                    target_locale TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL,
                    last_translated_source_hash TEXT NOT NULL,
                    target_value TEXT NOT NULL,
                    placeholder_signature TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    human_status TEXT NOT NULL,
                    is_current INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_conflict_identity
                ON memory_entries (project_id, key, source_locale, target_locale)
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '1.0')"
            )
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)


def _id_from_name(name: str) -> str:
    lowered = _lower_ascii(name)
    chars = []
    previous_dash = False
    for ch in lowered:
        if ch.isalnum():
            chars.append(ch)
            previous_dash = False
        elif ch in {"-", "_", "."}:
            if not previous_dash:
                chars.append("-")
                previous_dash = True
    result = "".join(chars).strip("-._")
    if not result:
        digest = sha256_text(name)[:12]
        return f"project-{digest}"
    if not result[0].isalnum():
        result = "project-" + result
    return result
