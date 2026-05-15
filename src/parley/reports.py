from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets

from parley.errors import FileIOError
from parley.serialization import pretty_json


_PROCESS_NONCE = secrets.token_hex(16)


@dataclass(frozen=True)
class PreparedReport:
    family: str
    path: Path
    content: str


def utc_now() -> str:
    override = os.environ.get("PARLEY_STARTED_AT")
    if override:
        return override
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compact_started_at(started_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", started_at)


def run_id_for(started_at: str) -> str:
    nonce = os.environ.get("PARLEY_PROCESS_NONCE_HEX") or _PROCESS_NONCE
    return f"{compact_started_at(started_at)}-{nonce}"


def prepare_report(
    *,
    project_root: Path,
    report_dir: Path,
    family: str,
    canonical_command: str,
    project_id: str,
    started_at: str,
    exit_code: int,
    inputs: dict,
    summary: dict,
    findings: list[dict] | None = None,
    failure_category: str | None = None,
) -> PreparedReport:
    run_id = run_id_for(started_at)
    filename = f"{canonical_command}--{run_id}.json"
    report_path = report_dir / family / filename
    finished_at = utc_now()
    payload = {
        "schema_version": "1.0",
        "report_family": family,
        "run_id": run_id,
        "project_id": project_id,
        "command": canonical_command,
        "project_root": str(project_root),
        "started_at": started_at,
        "created_at": finished_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "inputs": inputs,
        "summary": summary,
        "findings": sorted(findings or [], key=_finding_sort_key),
        "failure_category": failure_category,
    }
    return PreparedReport(family=family, path=report_path, content=pretty_json(payload))


def ensure_report_can_be_written(report: PreparedReport) -> None:
    if report.path.exists():
        raise FileIOError(f"report already exists: {report.path}")


def _finding_sort_key(finding: dict) -> tuple:
    severity_rank = {"blocking": 0, "error": 1, "warning": 2, "info": 3}
    return (
        str(finding.get("locale", "")),
        str(finding.get("path", "")),
        str(finding.get("localization_id", "")),
        str(finding.get("key", "")),
        str(finding.get("category", "")),
        severity_rank.get(str(finding.get("severity", "")), 4),
        str(finding.get("failure_category", "")),
        str(finding.get("code", "")),
        str(finding.get("stable_id", "")),
        str(finding.get("message", "")),
    )
