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

