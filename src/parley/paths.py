from __future__ import annotations

from pathlib import Path, PurePosixPath

from parley.errors import UsageError


def lexical_normalize(path: Path | str) -> str:
    raw = str(path).replace("\\", "/")
    absolute = raw.startswith("/")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
                continue
            if absolute:
                raise UsageError("path traversal escapes filesystem root")
            parts.append(part)
            continue
        parts.append(part)
    prefix = "/" if absolute else ""
    normalized = prefix + "/".join(parts)
    return normalized or ("/" if absolute else ".")


def canonical_relative_path(project_root: Path, input_path: Path | str, resolution_base: Path) -> str:
    input_path = Path(input_path)
    resolved = input_path if input_path.is_absolute() else resolution_base / input_path
    resolved_norm = lexical_normalize(resolved)
    root_norm = lexical_normalize(project_root)
    if resolved_norm != root_norm and not resolved_norm.startswith(root_norm.rstrip("/") + "/"):
        raise UsageError(f"path is outside project root: {input_path}")
    rel = resolved_norm[len(root_norm) :].lstrip("/")
    if not rel or rel.startswith("./") or rel.endswith("/"):
        raise UsageError(f"path does not resolve to a project file: {input_path}")
    validate_relative_path(rel)
    return rel


def canonical_localization_path(project_root: Path, manifest: dict, input_path: Path | str, resolution_base: Path) -> str:
    root = localization_root(project_root, manifest)
    return canonical_relative_path(root, input_path, resolution_base)


def localization_file_path(project_root: Path, manifest: dict, rel_path: str) -> Path:
    validate_relative_path(rel_path)
    return localization_root(project_root, manifest) / rel_path


def localization_root(project_root: Path, manifest: dict) -> Path:
    raw = manifest.get("project", {}).get("localization_root", ".")
    if not isinstance(raw, str) or not raw:
        raise UsageError("project.localization_root must be a non-empty string")
    if Path(raw).is_absolute() or "\\" in raw:
        raise UsageError("project.localization_root must be relative")
    normalized = lexical_normalize(project_root / raw)
    return Path(normalized)


def derive_init_localization_paths(project_root: Path, input_path: Path | str, resolution_base: Path) -> tuple[str, str]:
    input_path = Path(input_path)
    resolved = input_path if input_path.is_absolute() else resolution_base / input_path
    resolved_norm = lexical_normalize(resolved)
    project_norm = lexical_normalize(project_root)
    parent_norm = lexical_normalize(project_root.parent)
    if resolved_norm != project_norm and resolved_norm.startswith(project_norm.rstrip("/") + "/"):
        rel = resolved_norm[len(project_norm) :].lstrip("/")
        validate_relative_path(rel)
        return ".", rel
    if resolved_norm != parent_norm and resolved_norm.startswith(parent_norm.rstrip("/") + "/"):
        rel = resolved_norm[len(parent_norm) :].lstrip("/")
        if rel.startswith(project_root.name.rstrip("/") + "/"):
            raise UsageError(f"path is outside localization root: {input_path}")
        validate_relative_path(rel)
        return "..", rel
    raise UsageError(f"path is outside project localization root: {input_path}")


def validate_relative_path(path: str) -> None:
    if not path or path == ".":
        raise UsageError("relative path must not be empty")
    if path.startswith("/") or "\\" in path:
        raise UsageError(f"invalid relative path: {path}")
    if ":" in PurePosixPath(path).parts[0]:
        raise UsageError(f"invalid relative path: {path}")
    if any(part in {"", ".", ".."} for part in PurePosixPath(path).parts):
        raise UsageError(f"invalid relative path: {path}")


def resolve_report_dir(project_root: Path, report_dir: str | None) -> Path:
    report_root = project_root / "reports"
    if report_dir is None:
        return report_root
    path = Path(report_dir)
    base = report_root if not path.is_absolute() else Path("/")
    rel = canonical_relative_path(project_root, path, base)
    if rel != "reports" and not rel.startswith("reports/"):
        raise UsageError("--report-dir must resolve under <project-root>/reports/")
    return project_root / rel
