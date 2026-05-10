# Validation and Error Taxonomy Specification

## 1. Scope

This specification defines canonical validation categories, severity levels, finding shape, CI policy mapping, examples, and exit code interaction.

It is the authority for finding categories and severity names used by all other specs.

## 2. Severity Levels

| Severity | Meaning |
| --- | --- |
| `info` | Informational note; no quality risk by itself. |
| `warning` | Potential issue; should be reviewed. |
| `error` | Defect likely needing correction, but command may continue. |
| `blocking` | Defect that must block write, release, or CI success. |

Only `blocking` findings force CLI exit code `1` when the command otherwise completed.

## 3. Finding Categories

| Category | Description |
| --- | --- |
| `structural` | Missing keys, extra keys, duplicate keys, inventory/key baseline mismatches. |
| `parser_syntax` | File cannot be parsed cleanly according to parser grammar. |
| `localization_syntax` | Format-specific localization syntax issue that is parseable but invalid or risky. |
| `placeholder_integrity` | Placeholder, token, ICU, sentinel, or markup preservation issue. |
| `spelling` | Spelling issue. |
| `grammar` | Grammar or natural language correctness issue. |
| `clarity` | Ambiguous, confusing, or awkward text. |
| `terminology` | Glossary or terminology rule violation. |
| `semantic` | Meaning drift, mistranslation, contextual inconsistency, or semantic divergence. |
| `artifact_schema` | Invalid Parley artifact schema or unsupported artifact version. |
| `io` | File read/write or path issue represented in a report. |
| `provider` | Provider warning/error represented in a report. |

## 4. Finding Object

All reports MUST use the finding object defined in the artifact schema spec:

```json
{
  "id": "finding-001",
  "category": "placeholder_integrity",
  "severity": "blocking",
  "locale": "fr-FR",
  "file": "fr.lproj/Localizable.strings",
  "key": "welcome_message",
  "message": "Missing placeholder {name}.",
  "rationale": "The authoritative string contains {name}, but the target string does not.",
  "suggested_fix": "Restore {name} in the translated string.",
  "origin": "machine"
}
```

## 5. Default Severity Mapping

| Condition | Category | Severity |
| --- | --- | --- |
| Missing key relative to canonical inventory | `structural` | `blocking` |
| Extra key not in canonical inventory | `structural` | `warning` |
| Duplicate key | `structural` | `blocking` |
| Fatal parser syntax issue | `parser_syntax` | `blocking` |
| Recoverable parser syntax issue | `parser_syntax` | `error` |
| Missing placeholder | `placeholder_integrity` | `blocking` |
| Placeholder type mismatch | `placeholder_integrity` | `blocking` |
| Invalid placeholder reorder | `placeholder_integrity` | `error` |
| Glossary prohibited term used | `terminology` | `error` |
| Protected product name translated | `terminology` | `blocking` |
| Spelling issue | `spelling` | `warning` |
| Grammar issue | `grammar` | `warning` |
| Clarity issue | `clarity` | `warning` |
| Meaning drift from authoritative baseline | `semantic` | `error` |
| Severe mistranslation | `semantic` | `blocking` |
| Reportable artifact schema violation | `artifact_schema` | `blocking` |

## 6. CI Policy Mapping

Project validation policy may promote categories or severities to blocking:

```yaml
validation:
  policy:
    blocking_categories:
      - structural
      - placeholder_integrity
    blocking_severities:
      - blocking
```

Rules:

- Any finding whose severity is `blocking` is blocking.
- Any finding whose category is listed in `blocking_categories` is treated as blocking for exit code purposes.
- Policy promotion MUST NOT mutate the original finding severity. Reports SHOULD include `policy_blocked: true`.

## 7. Exit Code Interaction

| Scenario | Exit code |
| --- | --- |
| Validation completed and no blocking findings after policy | `0` |
| Validation completed with blocking findings after policy | `1` |
| Invalid CLI options or invalid Parley artifact schema | `2` |
| File cannot be read, parsed, or written | `3` |
| Required provider operation fails | `4` |

If an artifact schema problem prevents command startup, the command MUST exit `2`. If a command explicitly validates artifacts and can produce a report, it MAY include `artifact_schema` findings; blocking findings in that completed report use exit code `1`.

## 8. Examples

Missing canonical key:

```json
{
  "category": "structural",
  "severity": "blocking",
  "message": "Target localization is missing key ok_button."
}
```

Terminology violation:

```json
{
  "category": "terminology",
  "severity": "error",
  "message": "Preferred translation for Account is Compte."
}
```

Semantic drift:

```json
{
  "category": "semantic",
  "severity": "error",
  "message": "Target text changes the meaning from confirmation to cancellation."
}
```
