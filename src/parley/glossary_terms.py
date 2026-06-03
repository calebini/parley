from __future__ import annotations

from typing import Any

from parley.errors import UsageError


STATUSES = {"draft", "reviewed", "approved", "locked"}
SEVERITIES = {"info", "warning", "error", "blocking"}


def validate_glossary_artifact(data: dict[str, Any]) -> None:
    if not data.get("project_id") or not data.get("glossary_version"):
        raise UsageError("invalid glossary.yaml", failure_category="artifact_schema")
    if "terms" in data:
        if not isinstance(data["terms"], list):
            raise UsageError("glossary.yaml terms must be list", failure_category="artifact_schema")
        _validate_terms(data["terms"])
        return
    if "rules" in data:
        if not isinstance(data["rules"], list):
            raise UsageError("glossary.yaml rules must be list", failure_category="artifact_schema")
        return
    raise UsageError("invalid glossary.yaml", failure_category="artifact_schema")


def canonical_glossary(data: dict[str, Any]) -> dict[str, Any]:
    validate_glossary_artifact(data)
    if "terms" in data:
        return {
            "schema_version": "1.0",
            "project_id": data["project_id"],
            "glossary_version": data["glossary_version"],
            "terms": sorted([_canonical_term(term) for term in data["terms"]], key=lambda item: item["id"]),
        }
    return {
        "schema_version": "1.0",
        "project_id": data["project_id"],
        "glossary_version": data["glossary_version"],
        "terms": sorted(_legacy_rule_to_term(rule) for rule in data["rules"]),
    }


def glossary_findings(data: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        glossary = canonical_glossary(data)
    except UsageError as exc:
        return [
            _glossary_finding(
                code="artifact_schema",
                message=str(exc),
                severity="blocking",
                term_id=None,
            )
        ]
    seen_ids: set[str] = set()
    seen_sources: dict[tuple[str, str], str] = {}
    for term in glossary["terms"]:
        term_id = term["id"]
        if term_id in seen_ids:
            findings.append(_glossary_finding("duplicate_term_id", f"duplicate glossary term id: {term_id}", "blocking", term_id))
        seen_ids.add(term_id)
        source_key = (_fold(term["source"], term.get("case_sensitive", False)), str(term.get("source_locale") or "*"))
        previous = seen_sources.get(source_key)
        if previous and previous != term_id:
            findings.append(
                _glossary_finding(
                    "terminology_ambiguous_glossary_match",
                    f"multiple glossary terms match source: {term['source']}",
                    "warning",
                    term_id,
                )
            )
        seen_sources[source_key] = term_id
    return findings


def resolve_constraints(
    glossary: dict[str, Any] | None,
    *,
    source_text: str,
    source_locale: str,
    target_locale: str,
) -> list[dict[str, Any]]:
    if not glossary:
        return []
    canonical = canonical_glossary(glossary)
    constraints = []
    for term in canonical["terms"]:
        if not _locale_applies(term.get("source_locale") or source_locale, source_locale):
            continue
        if not _contains(source_text, term["source"], term.get("case_sensitive", False)):
            continue
        target = _target_for(term, target_locale)
        forbidden = _forbidden_for(term, target_locale)
        constraints.append(
            {
                "id": term["id"],
                "source": term["source"],
                "source_locale": term.get("source_locale") or source_locale,
                "target_locale": target_locale,
                "preferred": target.get("term") if target else None,
                "status": target.get("status", "draft") if target else "draft",
                "severity": target.get("severity") if target else None,
                "forbidden": forbidden,
                "protected": bool(term.get("protected")),
                "untranslated": bool(term.get("untranslated")),
                "case_sensitive": bool(term.get("case_sensitive")),
                "notes": target.get("notes") if target and target.get("notes") is not None else term.get("notes"),
            }
        )
    return constraints


def terminology_findings(
    glossary: dict[str, Any] | None,
    *,
    key: str,
    path: str,
    locale: str,
    source_text: str,
    target_text: str,
    source_locale: str,
) -> list[dict[str, Any]]:
    findings = []
    for constraint in resolve_constraints(glossary, source_text=source_text, source_locale=source_locale, target_locale=locale):
        preferred = constraint.get("preferred")
        if preferred and not _contains(target_text, str(preferred), bool(constraint.get("case_sensitive"))):
            findings.append(
                _terminology_finding(
                    path=path,
                    locale=locale,
                    key=key,
                    code="terminology_glossary_preferred_term_mistranslated",
                    message=f"preferred translation for {constraint['source']} is {preferred}",
                    severity=_constraint_severity(constraint),
                    term_id=constraint["id"],
                )
            )
        for forbidden in constraint.get("forbidden", []):
            if _contains(target_text, str(forbidden), bool(constraint.get("case_sensitive"))):
                findings.append(
                    _terminology_finding(
                        path=path,
                        locale=locale,
                        key=key,
                        code="terminology_glossary_prohibited_term",
                        message=f"prohibited glossary term used: {forbidden}",
                        severity="error",
                        term_id=constraint["id"],
                    )
                )
        if constraint.get("protected") and not _contains(target_text, str(constraint["source"]), bool(constraint.get("case_sensitive"))):
            findings.append(
                _terminology_finding(
                    path=path,
                    locale=locale,
                    key=key,
                    code="terminology_protected_product_name_translated",
                    message=f"protected glossary term altered: {constraint['source']}",
                    severity="blocking",
                    term_id=constraint["id"],
                )
            )
        if constraint.get("untranslated") and not _contains(target_text, str(constraint["source"]), bool(constraint.get("case_sensitive"))):
            findings.append(
                _terminology_finding(
                    path=path,
                    locale=locale,
                    key=key,
                    code="terminology_untranslated_term_translated",
                    message=f"untranslated glossary term changed: {constraint['source']}",
                    severity="error",
                    term_id=constraint["id"],
                )
            )
    return findings


def _validate_terms(terms: list[Any]) -> None:
    for term in terms:
        if not isinstance(term, dict):
            raise UsageError("glossary term must be object", failure_category="artifact_schema")
        if not isinstance(term.get("id"), str) or not term["id"]:
            raise UsageError("glossary term missing id", failure_category="artifact_schema")
        if not isinstance(term.get("source"), str) or not term["source"]:
            raise UsageError("glossary term missing source", failure_category="artifact_schema")
        if "targets" in term and not isinstance(term["targets"], dict):
            raise UsageError("glossary term targets must be object", failure_category="artifact_schema")
        for locale, target in term.get("targets", {}).items():
            if not isinstance(locale, str) or not locale:
                raise UsageError("glossary target locale must be non-empty", failure_category="artifact_schema")
            if not isinstance(target, dict) or not isinstance(target.get("term"), str) or not target["term"]:
                raise UsageError("glossary target missing term", failure_category="artifact_schema")
            if target.get("status", "draft") not in STATUSES:
                raise UsageError("glossary target status is invalid", failure_category="artifact_schema")
            if target.get("severity", "warning") not in SEVERITIES:
                raise UsageError("glossary target severity is invalid", failure_category="artifact_schema")
        if "forbidden" in term and not isinstance(term["forbidden"], dict):
            raise UsageError("glossary term forbidden must be object", failure_category="artifact_schema")
        for forbidden in term.get("forbidden", {}).values():
            if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
                raise UsageError("glossary forbidden values must be non-empty strings", failure_category="artifact_schema")


def _canonical_term(term: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": term["id"],
        "source": term["source"],
        **({"source_locale": _lower_ascii(term["source_locale"])} if term.get("source_locale") else {}),
        **({"part_of_speech": term["part_of_speech"]} if term.get("part_of_speech") else {}),
        **({"notes": term["notes"]} if term.get("notes") else {}),
        **({"case_sensitive": bool(term["case_sensitive"])} if "case_sensitive" in term else {}),
        **({"protected": bool(term["protected"])} if "protected" in term else {}),
        **({"untranslated": bool(term["untranslated"])} if "untranslated" in term else {}),
        **({"targets": _canonical_targets(term["targets"])} if term.get("targets") else {}),
        **({"forbidden": _canonical_forbidden(term["forbidden"])} if term.get("forbidden") else {}),
    }


def _canonical_targets(targets: dict[str, Any]) -> dict[str, Any]:
    canonical = {}
    for locale, target in sorted(targets.items()):
        item = {"term": target["term"]}
        if target.get("status"):
            item["status"] = target["status"]
        if target.get("severity"):
            item["severity"] = target["severity"]
        if "case_sensitive" in target:
            item["case_sensitive"] = bool(target["case_sensitive"])
        if target.get("notes"):
            item["notes"] = target["notes"]
        canonical[_lower_ascii(locale)] = item
    return canonical


def _canonical_forbidden(forbidden: dict[str, list[str]]) -> dict[str, list[str]]:
    return {_lower_ascii(locale): sorted(values) for locale, values in sorted(forbidden.items())}


def _legacy_rule_to_term(rule: Any) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise UsageError("legacy glossary rule must be object", failure_category="artifact_schema")
    source = str(rule.get("term") or "")
    if not source:
        raise UsageError("legacy glossary rule missing term", failure_category="artifact_schema")
    term_id = str(rule.get("id") or _slug(source))
    target_locale = _lower_ascii(str(rule.get("target_locale") or "*"))
    rule_type = rule.get("type", "preferred")
    term: dict[str, Any] = {"id": term_id, "source": source}
    if rule.get("source_locale"):
        term["source_locale"] = _lower_ascii(str(rule["source_locale"]))
    if rule.get("notes"):
        term["notes"] = str(rule["notes"])
    if rule_type in {"protected", "canonical"}:
        term["protected"] = True
    if rule_type == "untranslated":
        term["untranslated"] = True
    if rule_type == "prohibited":
        term["forbidden"] = {target_locale: [str(rule.get("translation") or source)]}
    elif rule.get("translation"):
        target = {"term": str(rule["translation"])}
        if rule.get("severity"):
            target["severity"] = str(rule["severity"])
        term["targets"] = {target_locale: target}
    return _canonical_term(term)


def _target_for(term: dict[str, Any], target_locale: str) -> dict[str, Any]:
    targets = term.get("targets", {})
    return targets.get(_lower_ascii(target_locale)) or targets.get("*") or {}


def _forbidden_for(term: dict[str, Any], target_locale: str) -> list[str]:
    forbidden = term.get("forbidden", {})
    return list(forbidden.get(_lower_ascii(target_locale), [])) + list(forbidden.get("*", []))


def _locale_applies(scope: str, locale: str) -> bool:
    return scope == "*" or _lower_ascii(scope) == _lower_ascii(locale)


def _contains(text: str, term: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return term in text
    return term.lower() in text.lower()


def _constraint_severity(constraint: dict[str, Any]) -> str:
    if constraint.get("severity"):
        return str(constraint["severity"])
    return "error" if constraint.get("status") in {"approved", "locked"} else "warning"


def _terminology_finding(*, path: str, locale: str, key: str, code: str, message: str, severity: str, term_id: str) -> dict[str, Any]:
    return {
        "stable_id": "|".join([path, code, key, term_id]),
        "severity": severity,
        "category": "terminology",
        "failure_category": code,
        "path": path,
        "locale": locale,
        "localization_id": None,
        "key": key,
        "code": code,
        "message": message,
        "term_id": term_id,
    }


def _glossary_finding(code: str, message: str, severity: str, term_id: str | None) -> dict[str, Any]:
    return {
        "stable_id": "|".join(["glossary.yaml", code, term_id or ""]),
        "severity": severity,
        "category": "terminology" if code.startswith("terminology_") else "artifact_schema",
        "failure_category": code,
        "path": "glossary.yaml",
        "locale": None,
        "localization_id": None,
        "key": None,
        "code": code,
        "message": message,
        "term_id": term_id,
    }


def _slug(value: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "-" for ch in value]
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return slug or "term"


def _fold(value: str, case_sensitive: bool) -> str:
    return value if case_sensitive else value.lower()


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
