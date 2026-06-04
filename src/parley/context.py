from __future__ import annotations

from pathlib import Path

from parley.artifacts import load_project_artifacts, resolve_project_root, schema_issues_for_required
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_OK, EXIT_USAGE_OR_SCHEMA, FileIOError, ParleyError
from parley.paths import resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.validation import CommandResult


def context_validate(*, project_root: str | None, report_dir: str | None, cwd: Path) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=True, include_context=False)
        assert artifacts.canonical_inventory is not None
        context_issues = schema_issues_for_required(root, ["context-anchor.yaml"])
        findings = []
        context_anchor = None
        if context_issues:
            for issue in context_issues:
                findings.append(
                    _finding(
                        code="context_anchor_" + issue.status,
                        message=issue.message,
                        failure_category=issue.status,
                    )
                )
        else:
            context_anchor = load_project_artifacts(root, include_canonical=False, include_context=True).context_anchor
            findings.extend(_context_findings(context_anchor or {}, artifacts.canonical_inventory))

        blocking_findings = [item for item in findings if item.get("severity") == "blocking"]
        context_complete = not blocking_findings
        exit_code = EXIT_BLOCKING_FINDINGS if blocking_findings else EXIT_OK
        summary = _summary(findings, artifacts.canonical_inventory)
        report = prepare_report(
            project_root=root,
            report_dir=resolve_report_dir(root, report_dir),
            family="validation",
            canonical_command="context_validate",
            project_id=artifacts.project_id,
            started_at=started_at,
            exit_code=exit_code,
            inputs={},
            summary=summary,
            findings=findings,
            failure_category="blocking_validation" if blocking_findings else None,
            extra_fields={
                "context_anchor_path": "context-anchor.yaml",
                "context_complete": context_complete,
                "validated_context": {
                    "path": "context-anchor.yaml",
                    "status": "validated" if context_complete else "incomplete",
                },
            },
        )
        _write_report_only(report)
        return CommandResult(exit_code, [report.path], payload={"context_complete": context_complete})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def _context_findings(context_anchor: dict, canonical: dict) -> list[dict]:
    findings = []
    entries = context_anchor.get("entries", {})
    canonical_keys = set(canonical["entries"])
    entry_keys = set(entries)
    for key in sorted(canonical_keys - entry_keys):
        findings.append(
            _finding(
                code="context_missing_key",
                message=f"context missing for key: {key}",
                failure_category="context_incomplete",
                key=key,
            )
        )
    for key in sorted(canonical_keys & entry_keys):
        value = _context_value(entries[key])
        if not isinstance(value, str) or not value.strip():
            findings.append(
                _finding(
                    code="context_blank",
                    message=f"context is blank for key: {key}",
                    failure_category="context_incomplete",
                    key=key,
                )
            )
    for key in sorted(entry_keys - canonical_keys):
        findings.append(
            _finding(
                code="context_stale_key",
                message=f"context entry has no canonical key: {key}",
                failure_category="stale_context",
                key=key,
                severity="warning",
            )
        )
    return findings


def _context_value(entry) -> str | None:
    if isinstance(entry, dict):
        value = entry.get("context") or entry.get("description") or entry.get("context_description")
    else:
        value = entry
    return value if isinstance(value, str) else None


def _finding(
    *,
    code: str,
    message: str,
    failure_category: str,
    key: str | None = None,
    severity: str = "blocking",
) -> dict:
    return {
        "stable_id": "|".join(str(part) for part in ["context-anchor.yaml", code, key or ""]),
        "severity": severity,
        "category": "context",
        "failure_category": failure_category,
        "path": "context-anchor.yaml",
        "locale": None,
        "localization_id": None,
        "key": key,
        "code": code,
        "message": message,
    }


def _summary(findings: list[dict], canonical: dict) -> dict:
    return {
        "canonical_key_count": len(canonical["entries"]),
        "finding_count": len(findings),
        "missing_count": sum(1 for item in findings if item["code"] == "context_missing_key"),
        "blank_count": sum(1 for item in findings if item["code"] == "context_blank"),
        "stale_count": sum(1 for item in findings if item["code"] == "context_stale_key"),
    }


def _write_report_only(report) -> None:
    if report.path.exists():
        raise FileIOError(f"report already exists: {report.path}")
    report.path.parent.mkdir(parents=True, exist_ok=True)
    report.path.write_text(report.content, encoding="utf-8")
