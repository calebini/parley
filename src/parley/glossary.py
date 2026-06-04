from __future__ import annotations

from pathlib import Path
import sqlite3

from parley.artifacts import load_project_artifacts, read_yaml_artifact, resolve_project_root
from parley.atomic import commit_files
from parley.errors import EXIT_BLOCKING_FINDINGS, EXIT_OK, EXIT_USAGE_OR_SCHEMA, FileIOError, ParleyError, UsageError
from parley.glossary_terms import canonical_glossary, glossary_findings
from parley.paths import resolve_report_dir
from parley.reports import prepare_report, utc_now
from parley.serialization import yaml_dump
from parley.validation import CommandResult


def glossary_init(
    *,
    project_root: str | None,
    force: bool,
    with_example: bool,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False, include_context=False)
        glossary_path = root / "glossary.yaml"
        if glossary_path.exists() and not force:
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], "glossary.yaml already exists; pass --force to replace it")
        glossary = _empty_glossary(artifacts.project_id)
        content = _example_glossary_text(artifacts.project_id) if with_example else yaml_dump(glossary)
        report = _glossary_report(
            root=root,
            report_dir=report_dir,
            started_at=started_at,
            command="glossary_init",
            project_id=artifacts.project_id,
            exit_code=EXIT_OK,
            inputs={"force": force, "with_example": with_example},
            summary={"term_count": 1 if with_example else 0, "glossary_written": True},
            findings=[],
        )
        commit_files(root, {glossary_path: content.encode("utf-8")}, {report.path: report.content})
        return CommandResult(EXIT_OK, [report.path])
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def glossary_import(
    *,
    project_root: str | None,
    file: str,
    merge_mode: str,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False, include_context=False)
        incoming = canonical_glossary(read_yaml_artifact(Path(file).absolute()))
        if incoming["project_id"] != artifacts.project_id:
            return CommandResult(EXIT_USAGE_OR_SCHEMA, [], "glossary project_id does not match project")
        current = canonical_glossary(artifacts.glossary) if artifacts.glossary else _empty_glossary(artifacts.project_id)
        if merge_mode == "replace":
            result = incoming
        else:
            result = _merge_glossaries(current, incoming)
        findings = glossary_findings(result)
        exit_code = EXIT_BLOCKING_FINDINGS if any(item["severity"] == "blocking" for item in findings) else EXIT_OK
        report = _glossary_report(
            root=root,
            report_dir=report_dir,
            started_at=started_at,
            command="glossary_import",
            project_id=artifacts.project_id,
            exit_code=exit_code,
            inputs={"file": str(Path(file).absolute()), "merge_mode": merge_mode},
            summary={"term_count": len(result["terms"]), "finding_count": len(findings), "glossary_written": exit_code == EXIT_OK},
            findings=findings,
        )
        files = {root / "glossary.yaml": yaml_dump(result).encode("utf-8")} if exit_code == EXIT_OK else {}
        commit_files(root, files, {report.path: report.content})
        return CommandResult(exit_code, [report.path])
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def glossary_list(*, project_root: str | None, locale: str | None, query: str | None, cwd: Path) -> CommandResult:
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False, include_context=False)
        glossary = canonical_glossary(artifacts.glossary) if artifacts.glossary else _empty_glossary(artifacts.project_id)
        rows = _term_rows(glossary, locale=locale, query=query)
        return CommandResult(EXIT_OK, [], payload={"project_root": str(root), "terms": rows})
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def glossary_validate(*, project_root: str | None, report_dir: str | None, cwd: Path) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=False, include_context=False)
        glossary = canonical_glossary(artifacts.glossary) if artifacts.glossary else _empty_glossary(artifacts.project_id)
        findings = glossary_findings(glossary)
        exit_code = EXIT_BLOCKING_FINDINGS if any(item["severity"] == "blocking" for item in findings) else EXIT_OK
        report = _glossary_report(
            root=root,
            report_dir=report_dir,
            started_at=started_at,
            command="glossary_validate",
            project_id=artifacts.project_id,
            exit_code=exit_code,
            inputs={},
            summary={"term_count": len(glossary["terms"]), "finding_count": len(findings)},
            findings=findings,
        )
        _write_report_only(report)
        return CommandResult(exit_code, [report.path])
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def glossary_suggest_from_tm(
    *,
    project_root: str | None,
    target_locale: str | None,
    report_dir: str | None,
    cwd: Path,
) -> CommandResult:
    started_at = utc_now()
    try:
        root = resolve_project_root(project_root, cwd)
        artifacts = load_project_artifacts(root, include_canonical=True, include_context=False)
        assert artifacts.canonical_inventory is not None
        suggestions = _tm_suggestions(root, artifacts, _lower_ascii(target_locale) if target_locale else None)
        report = _glossary_report(
            root=root,
            report_dir=report_dir,
            started_at=started_at,
            command="glossary_suggest",
            project_id=artifacts.project_id,
            exit_code=EXIT_OK,
            inputs={"from_tm": True, "target_locale": _lower_ascii(target_locale) if target_locale else None},
            summary={"suggestion_count": len(suggestions), "glossary_written": False},
            findings=[],
            extra_fields={"suggested_terms": suggestions},
        )
        _write_report_only(report)
        return CommandResult(EXIT_OK, [report.path], payload={"suggested_terms": suggestions})
    except sqlite3.DatabaseError as exc:
        return CommandResult(EXIT_USAGE_OR_SCHEMA, [], f"invalid translation-memory.sqlite: {exc}")
    except ParleyError as exc:
        return CommandResult(exc.exit_code, [], str(exc))


def _merge_glossaries(current: dict, incoming: dict) -> dict:
    terms = {term["id"]: term for term in current["terms"]}
    for term in incoming["terms"]:
        if term["id"] in terms and terms[term["id"]] != term:
            raise UsageError(f"conflicting glossary term id: {term['id']}")
        terms[term["id"]] = term
    return {
        "schema_version": "1.0",
        "project_id": current["project_id"],
        "glossary_version": incoming["glossary_version"],
        "terms": sorted(terms.values(), key=lambda item: item["id"]),
    }


def _term_rows(glossary: dict, *, locale: str | None, query: str | None) -> list[dict]:
    normalized_locale = _lower_ascii(locale) if locale else None
    query_terms = [_lower_ascii(term) for term in (query or "").split() if term.strip()]
    rows = []
    for term in glossary["terms"]:
        targets = term.get("targets", {})
        forbidden = term.get("forbidden", {})
        applicable_locales = sorted(set([*targets, *forbidden]) or ["*"])
        for target_locale in applicable_locales:
            if normalized_locale and target_locale not in {normalized_locale, "*"}:
                continue
            target = targets.get(target_locale, {})
            row = {
                "id": term["id"],
                "source": term["source"],
                "source_locale": term.get("source_locale", ""),
                "target_locale": target_locale,
                "target": target.get("term", ""),
                "status": target.get("status", ""),
                "protected": term.get("protected", False),
                "untranslated": term.get("untranslated", False),
                "forbidden": ", ".join(forbidden.get(target_locale, [])),
                "notes": target.get("notes") or term.get("notes", ""),
            }
            haystack = _lower_ascii(" ".join(str(value) for value in row.values()))
            if query_terms and not all(item in haystack for item in query_terms):
                continue
            rows.append(row)
    return sorted(rows, key=lambda item: (item["source"], item["target_locale"], item["id"]))


def _tm_suggestions(root: Path, artifacts, target_locale: str | None) -> list[dict]:
    canonical_entries = artifacts.canonical_inventory["entries"]
    suggestions = []
    with sqlite3.connect(root / artifacts.manifest["artifacts"]["translation_memory"]) as conn:
        rows = conn.execute(
            """
            SELECT key, target_locale, target_value, human_status
            FROM memory_entries
            WHERE is_current = 1
            ORDER BY target_locale, key
            """
        ).fetchall()
    for key, row_locale, target_value, human_status in rows:
        row_locale = str(row_locale)
        if target_locale and row_locale != target_locale:
            continue
        source = canonical_entries.get(str(key), {}).get("authoritative_value")
        if not source:
            continue
        suggestions.append(
            {
                "id": f"{_slug(str(key))}-{row_locale}",
                "source": source,
                "targets": {
                    row_locale: {
                        "term": str(target_value),
                        "status": "draft",
                        "notes": f"suggested from current TM record with human_status={human_status}",
                    }
                },
            }
        )
    return suggestions


def _glossary_report(
    *,
    root: Path,
    report_dir: str | None,
    started_at: str,
    command: str,
    project_id: str,
    exit_code: int,
    inputs: dict,
    summary: dict,
    findings: list[dict],
    extra_fields: dict | None = None,
):
    return prepare_report(
        project_root=root,
        report_dir=resolve_report_dir(root, report_dir),
        family="glossary",
        canonical_command=command,
        project_id=project_id,
        started_at=started_at,
        exit_code=exit_code,
        inputs=inputs,
        summary=summary,
        findings=findings,
        failure_category=None if exit_code == EXIT_OK else "blocking_validation",
        extra_fields=extra_fields,
    )


def _write_report_only(report) -> None:
    if report.path.exists():
        raise FileIOError(f"report already exists: {report.path}")
    report.path.parent.mkdir(parents=True, exist_ok=True)
    report.path.write_text(report.content, encoding="utf-8")


def _empty_glossary(project_id: str) -> dict:
    return {"schema_version": "1.0", "project_id": project_id, "glossary_version": "mvp", "terms": []}


def _example_glossary_text(project_id: str) -> str:
    return f'''schema_version: "1.0"
project_id: "{project_id}"
glossary_version: "mvp"
terms:
  -
    id: "replace-with-stable-term-id"
    source: "Replace with the exact source term or phrase to detect"
    source_locale: "en-us"
    part_of_speech: "Replace with noun, verb, adjective, product_name, acronym, or phrase"
    notes: "Explain where this term appears and any usage nuance translators should know."
    targets:
      fr-fr:
        term: "Replace with the preferred translation for this locale"
        status: "draft"
        severity: "warning"
        notes: "Explain why this translation is preferred or when to use it."
      de-de:
        term: "Replace with the preferred translation for another locale"
    forbidden:
      fr-fr:
        - "Replace with a translation that should not be used"
      de-de:
        - "Optional: replace with a disallowed translation for another locale"
'''


def _slug(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "-" for ch in value]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or "term"


def _lower_ascii(value: str | None) -> str:
    value = value or ""
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
