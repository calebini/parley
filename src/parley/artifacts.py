from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

from parley.errors import UsageError
from parley.serialization import yaml_load


ARTIFACT_ORDER = [
    "parley.yaml",
    "inventory.yaml",
    "canonical-inventory.json",
    "context-anchor.yaml",
    "glossary.yaml",
    "translation-memory.sqlite",
    "reports",
    ".parley",
]


@dataclass(frozen=True)
class ArtifactIssue:
    artifact: str
    status: str
    message: str


@dataclass(frozen=True)
class ProjectArtifacts:
    project_root: Path
    manifest: dict[str, Any]
    inventory: dict[str, Any]
    canonical_inventory: dict[str, Any] | None = None
    context_anchor: dict[str, Any] | None = None
    glossary: dict[str, Any] | None = None

    @property
    def project_id(self) -> str:
        return str(self.manifest["project"]["id"])


def find_project_root(start: Path) -> Path | None:
    current = start.absolute()
    if current.is_file():
        current = current.parent
    while True:
        if (current / "parley.yaml").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def resolve_project_root(project_root: str | None, cwd: Path) -> Path:
    if project_root:
        return Path(project_root).absolute()
    found = find_project_root(cwd)
    if found is None:
        raise UsageError("no Parley project root found")
    return found


def read_yaml_artifact(path: Path) -> dict[str, Any]:
    try:
        data = yaml_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"unable to read {path.name}", failure_category="io") from exc
    except ValueError as exc:
        raise UsageError(f"schema-invalid {path.name}", failure_category="artifact_schema") from exc
    if not isinstance(data, dict):
        raise UsageError(f"schema-invalid {path.name}", failure_category="artifact_schema")
    return data


def read_json_artifact(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"unable to read {path.name}", failure_category="io") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"schema-invalid {path.name}", failure_category="artifact_schema") from exc
    if not isinstance(data, dict):
        raise UsageError(f"schema-invalid {path.name}", failure_category="artifact_schema")
    return data


def inspect_artifacts(project_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for artifact in ARTIFACT_ORDER:
        path = project_root / artifact
        kind = "directory" if artifact in {"reports", ".parley"} else "file"
        status = _artifact_status(path, artifact, kind)
        rows.append({"artifact": artifact, "path": str(path), "kind": kind, "status": status})
    return rows


def _artifact_status(path: Path, artifact: str, kind: str) -> str:
    if not path.exists():
        return "missing"
    if kind == "directory":
        return "present" if path.is_dir() else "io_error"
    if not path.is_file():
        return "io_error"
    try:
        if artifact.endswith(".yaml"):
            data = read_yaml_artifact(path)
            _validate_yaml_artifact(artifact, data)
        elif artifact.endswith(".json"):
            data = read_json_artifact(path)
            _validate_json_artifact(artifact, data)
        elif artifact.endswith(".sqlite"):
            _validate_sqlite(path)
    except UsageError as exc:
        return "io_error" if exc.failure_category == "io" else "schema_invalid"
    return "present"


def load_project_artifacts(project_root: Path, *, include_canonical: bool = True) -> ProjectArtifacts:
    manifest = read_yaml_artifact(project_root / "parley.yaml")
    _validate_yaml_artifact("parley.yaml", manifest)
    inventory = read_yaml_artifact(project_root / "inventory.yaml")
    _validate_yaml_artifact("inventory.yaml", inventory)
    canonical = None
    if include_canonical:
        canonical = read_json_artifact(project_root / "canonical-inventory.json")
        _validate_json_artifact("canonical-inventory.json", canonical)
    context = None
    if (project_root / "context-anchor.yaml").exists():
        context = read_yaml_artifact(project_root / "context-anchor.yaml")
        _validate_yaml_artifact("context-anchor.yaml", context)
    glossary = None
    if (project_root / "glossary.yaml").exists():
        glossary = read_yaml_artifact(project_root / "glossary.yaml")
        _validate_yaml_artifact("glossary.yaml", glossary)
    return ProjectArtifacts(project_root, manifest, inventory, canonical, context, glossary)


def schema_issues_for_required(project_root: Path, required: list[str]) -> list[ArtifactIssue]:
    issues: list[ArtifactIssue] = []
    for artifact in required:
        path = project_root / artifact
        if not path.exists():
            issues.append(ArtifactIssue(artifact, "missing", f"{artifact} is missing"))
            continue
        status = _artifact_status(path, artifact, "file")
        if status != "present":
            issues.append(ArtifactIssue(artifact, status, f"{artifact} is {status}"))
    return issues


def _validate_yaml_artifact(artifact: str, data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0":
        raise UsageError(f"{artifact} must have schema_version 1.0", failure_category="artifact_schema")
    if artifact == "parley.yaml":
        project = data.get("project")
        artifacts = data.get("artifacts")
        if not isinstance(project, dict) or not isinstance(artifacts, dict):
            raise UsageError("invalid parley.yaml", failure_category="artifact_schema")
        for field in ["id", "name", "authoritative_localization_id", "authoritative_locale"]:
            if not project.get(field):
                raise UsageError(f"parley.yaml missing project.{field}", failure_category="artifact_schema")
        for field in ["inventory", "canonical_inventory", "context_anchor", "glossary", "translation_memory"]:
            if not artifacts.get(field):
                raise UsageError(f"parley.yaml missing artifacts.{field}", failure_category="artifact_schema")
    elif artifact == "inventory.yaml":
        if not data.get("project_id") or not isinstance(data.get("localizations"), list):
            raise UsageError("invalid inventory.yaml", failure_category="artifact_schema")
        seen = set()
        for record in data["localizations"]:
            if not isinstance(record, dict):
                raise UsageError("invalid inventory record", failure_category="artifact_schema")
            for field in ["localization_id", "locale", "format", "path", "role", "status", "parser"]:
                if not record.get(field):
                    raise UsageError(f"inventory record missing {field}", failure_category="artifact_schema")
            if record["localization_id"] in seen:
                raise UsageError("duplicate localization_id", failure_category="artifact_schema")
            seen.add(record["localization_id"])
    elif artifact == "context-anchor.yaml":
        if not data.get("project_id") or not data.get("authoritative_locale") or not isinstance(data.get("entries"), dict):
            raise UsageError("invalid context-anchor.yaml", failure_category="artifact_schema")
    elif artifact == "glossary.yaml":
        if not data.get("project_id") or not data.get("glossary_version") or not isinstance(data.get("rules"), list):
            raise UsageError("invalid glossary.yaml", failure_category="artifact_schema")


def _validate_json_artifact(artifact: str, data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0":
        raise UsageError(f"{artifact} must have schema_version 1.0", failure_category="artifact_schema")
    if artifact == "canonical-inventory.json":
        for field in [
            "project_id",
            "authoritative_localization_id",
            "authoritative_locale",
            "authoritative_format",
            "generated_at",
            "inventory_hash",
            "entries",
        ]:
            if field not in data:
                raise UsageError(f"canonical-inventory.json missing {field}", failure_category="artifact_schema")
        if not isinstance(data["entries"], dict):
            raise UsageError("canonical-inventory entries must be object", failure_category="artifact_schema")


def _validate_sqlite(path: Path) -> None:
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()
    except sqlite3.DatabaseError as exc:
        raise UsageError("invalid translation-memory.sqlite", failure_category="artifact_schema") from exc
    if not row or row[0] != "1.0":
        raise UsageError("translation-memory.sqlite missing schema_version", failure_category="artifact_schema")

