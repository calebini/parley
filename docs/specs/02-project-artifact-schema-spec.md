# Project Artifact Schema Specification

## 1. Scope

This specification defines v1 project artifacts and machine-readable schemas for project configuration, inventory, canonical string inventory, context anchors, glossary rules, reports, and translation memory import/export.

All v1 artifacts MUST use `schema_version: "1.0"` or `"schema_version": "1.0"`.

## 2. Shared Types

### 2.1 Common Scalar Types

| Type | Definition |
| --- | --- |
| `ID` | Lowercase string matching `^[a-z0-9][a-z0-9._-]*$`. |
| `Locale` | BCP 47 locale string, such as `en-US` or `fr-FR`. |
| `Timestamp` | RFC 3339 UTC timestamp. |
| `Hash` | Lowercase SHA-256 hex digest. |
| `RelativePath` | Path relative to project root. Absolute paths MUST NOT be stored in project artifacts. |
| `ConfidenceScore` | Number from `0.0` to `1.0` inclusive. |

### 2.2 Enums

Localization formats:

- `ios_strings`
- `android_xml`

Localization roles:

- `authoritative`
- `target`

Human status:

- `draft`
- `reviewed`
- `approved`
- `locked`

Finding severities:

- `info`
- `warning`
- `error`
- `blocking`

Finding categories:

- `structural`
- `parser_syntax`
- `localization_syntax`
- `placeholder_integrity`
- `spelling`
- `grammar`
- `clarity`
- `terminology`
- `semantic`
- `artifact_schema`
- `io`
- `provider`

Confidence dimensions:

- `semantic`
- `contextual`
- `grammatical`
- `terminology_compliance`
- `placeholder_integrity`
- `clarity`

## 3. Hashing Rules

Unless a spec states otherwise, hashes MUST be SHA-256 over canonical JSON:

- UTF-8 encoding.
- Object keys sorted lexicographically.
- No insignificant whitespace.
- Null fields omitted.
- Arrays preserved in semantic order.

`content_hash` for localization entries MUST include:

- `key`
- `value`
- `locale`
- `format`
- `placeholder_signature`

## 4. `parley.yaml`

Human-authored project manifest.

Required fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project.id` | ID | Stable project ID. |
| `project.name` | string | Human-readable name. |
| `project.authoritative_localization_id` | ID | Inventory ID for authoritative localization. |
| `project.authoritative_locale` | Locale | Source language used as semantic baseline. |
| `artifacts.inventory` | RelativePath | Usually `inventory.yaml`. |
| `artifacts.canonical_inventory` | RelativePath | Usually `canonical-inventory.json`. |
| `artifacts.context_anchor` | RelativePath | Usually `context-anchor.yaml`. |
| `artifacts.glossary` | RelativePath | Usually `glossary.yaml`. |
| `artifacts.translation_memory` | RelativePath | Usually `translation-memory.sqlite`. |

Optional fields:

| Field | Type | Description |
| --- | --- | --- |
| `project.description` | string | Project-level context seed. |
| `defaults.provider` | string | Provider adapter name. |
| `defaults.report_format` | `json` | Only `json` is required for v1 reports. |
| `validation.policy` | object | CI blocking policy. |

Example:

```yaml
schema_version: "1.0"
project:
  id: myapp
  name: MyApp
  description: Consumer mobile application for account management.
  authoritative_localization_id: loc-en-us
  authoritative_locale: en-US
artifacts:
  inventory: inventory.yaml
  canonical_inventory: canonical-inventory.json
  context_anchor: context-anchor.yaml
  glossary: glossary.yaml
  translation_memory: translation-memory.sqlite
defaults:
  provider: openai
  report_format: json
validation:
  policy:
    blocking_categories:
      - structural
      - placeholder_integrity
    blocking_severities:
      - blocking
```

## 5. `inventory.yaml`

Required top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `localizations` | array | Localization file records. |

Localization record:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | ID | yes | Stable localization ID. |
| `locale` | Locale | yes | File locale. |
| `format` | enum | yes | `ios_strings` or `android_xml`. |
| `path` | RelativePath | yes | File path relative to project root. |
| `role` | enum | yes | `authoritative` or `target`. |
| `status` | enum | yes | `draft`, `reviewed`, `approved`, or `locked`. |
| `parser` | string | yes | Parser adapter ID. |
| `last_observed_hash` | Hash | no | Hash of parsed normalized file. |
| `last_validated_at` | Timestamp | no | Last validation time. |
| `metadata` | object | no | Implementation-specific metadata. |

Exactly one record MUST have `role: authoritative`.

## 6. `canonical-inventory.json`

Machine-managed structural baseline derived from the authoritative localization.

Top-level object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `project_id` | ID | yes | Project ID. |
| `authoritative_localization_id` | ID | yes | Inventory ID. |
| `authoritative_locale` | Locale | yes | Source locale. |
| `generated_at` | Timestamp | yes | Generation timestamp. |
| `inventory_hash` | Hash | yes | Hash of authoritative parsed file. |
| `entries` | object | yes | Map from localization key to canonical entry. |

Canonical entry:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | yes | Localization key. |
| `authoritative_value` | string | yes | Source value. |
| `value_hash` | Hash | yes | Hash of authoritative value. |
| `content_hash` | Hash | yes | Entry content hash. |
| `placeholder_signature` | string | yes | Normalized placeholder signature. |
| `placeholders` | array | yes | Placeholder token records. |
| `first_seen_at` | Timestamp | yes | First canonical inventory observation. |
| `last_updated_at` | Timestamp | yes | Last canonical value change. |
| `metadata` | object | no | Parser or project metadata. |

## 7. `context-anchor.yaml`

Human-reviewable semantic context artifact.

Top-level fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `project_id` | ID | yes | Project ID. |
| `authoritative_locale` | Locale | yes | Source language used for context. |
| `project_context.description` | string | yes | What the app/system is. |
| `project_context.domain` | string | no | Functional domain. |
| `project_context.considerations` | array of strings | no | Translation considerations. |
| `entries` | object | yes | Map from localization key to context entry. |

Context entry:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | yes | Localization key. |
| `context_description` | string | yes | Intended usage/meaning. |
| `confidence` | object | yes | Confidence dimension scores and aggregate. |
| `human_status` | enum | yes | `draft`, `reviewed`, `approved`, or `locked`. |
| `source` | `machine|human|imported` | yes | Origin of context. |
| `notes` | string | no | Optional reviewer notes. |
| `updated_at` | Timestamp | yes | Last update time. |

## 8. `glossary.yaml`

Top-level fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `project_id` | ID | yes | Project ID. |
| `glossary_version` | ID | yes | Stable glossary version. |
| `rules` | array | yes | Glossary rules. |

Glossary rule:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | ID | yes | Rule ID. |
| `term` | string | yes | Source term or phrase. |
| `type` | enum | yes | `preferred`, `prohibited`, `protected`, `untranslated`, or `canonical`. |
| `source_locale` | Locale | no | Locale for source term. |
| `target_locale` | Locale or `*` | no | Applies to target locale. |
| `translation` | string | no | Required or preferred target text. |
| `case_sensitive` | boolean | no | Defaults to `false`. |
| `severity` | severity enum | no | Defaults to `error`; `blocking` allowed. |
| `notes` | string | no | Human notes. |

## 9. Common Report Envelope

All report JSON files MUST use this top-level shape:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `report_type` | enum | yes | `validation`, `confidence`, `comparison`, `translation`, `translation_memory`, or `initialization`. |
| `run_id` | ID/string | yes | Unique invocation ID. |
| `project_id` | ID/null | yes | Null for non-project paired workflows. |
| `command` | string | yes | CLI command name. |
| `created_at` | Timestamp | yes | Report creation time. |
| `inputs` | object | yes | Command-specific inputs. |
| `provider` | object/null | yes | Provider metadata when used. |
| `summary` | object | yes | Aggregate counts/scores. |
| `findings` | array | yes | Validation or comparison findings. |
| `entries` | array | no | Command-specific per-key details. |

Finding object:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | ID/string | yes | Stable finding ID within report. |
| `category` | finding category enum | yes | Shared category. |
| `severity` | severity enum | yes | Shared severity. |
| `locale` | Locale/null | yes | Locale when applicable. |
| `file` | RelativePath/null | yes | File path when applicable. |
| `key` | string/null | yes | Localization key when applicable. |
| `message` | string | yes | Human-readable finding. |
| `rationale` | string | no | Why this finding was emitted. |
| `suggested_fix` | string | no | Suggested remediation. |
| `origin` | `machine|human|provider` | yes | Finding source. |

## 10. Translation Memory Import/Export

Translation memory import/export MUST use JSON Lines. Each line is one record using the schema from [Translation Memory Specification](08-translation-memory-spec.md).

Required JSONL fields:

- `schema_version`
- `memory_id`
- `project_id`
- `source_locale`
- `target_locale`
- `key`
- `source_text`
- `target_text`
- `source_content_hash`
- `placeholder_signature`
- `provenance`
- `approval_status`
- `confidence`
- `created_at`
- `updated_at`

