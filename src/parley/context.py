from __future__ import annotations

from pathlib import Path

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.atomic import commit_files
from parley.errors import EXIT_OK, EXIT_USAGE_OR_SCHEMA, ParleyError
from parley.serialization import yaml_dump
from parley.validation import CommandResult


def context_seed(*, project_root: str | None, mode: str, cwd: Path) -> CommandResult:
    try:
        root = resolve_project_root(project_root, cwd)
        artifact_issues = schema_issues_for_required(root, ["parley.yaml", "canonical-inventory.json"])
        if artifact_issues:
            message = "; ".join(issue.message for issue in artifact_issues)
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], message)
        artifacts = load_project_artifacts(root, include_canonical=True)
        assert artifacts.canonical_inventory is not None
        canonical = artifacts.canonical_inventory
        anchor = {
            "schema_version": "1.0",
            "project_id": artifacts.project_id,
            "authoritative_locale": canonical["authoritative_locale"],
            "project_context": {"description": "Placeholder context generated for local MVP dry runs."},
            "entries": {
                key: {"context": _placeholder_context(key, mode)}
                for key in sorted(canonical["entries"])
            },
        }
        commit_files(root, {root / "context-anchor.yaml": yaml_dump(anchor).encode("utf-8")}, {})
        return CommandResult(
            EXIT_OK,
            [],
            payload={
                "context_anchor": str(root / "context-anchor.yaml"),
                "entry_count": len(anchor["entries"]),
                "mode": mode,
            },
        )
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def _placeholder_context(key: str, mode: str) -> str:
    return f"Placeholder context for {key} ({mode})."
