# Project Artifact Schema Specification

## 1. Scope

This specification defines the MVP project artifact contract for Parley project mode. It is the build authority for the required files under a Parley project root, their minimum required fields, artifact ownership, artifact mutation boundaries, and the shared report envelope used by command-specific reports.

Architecture authority for MVP boundaries is the Parley High-Level Design (HLD). The v1 spec index is dependency/navigation context only.

For the MVP, Parley is project-first:

- Project artifacts live under a resolved `<project-root>`.
- Reports are project-scoped under `<project-root>/reports/` or a command-resolved report directory that remains inside that project report root.
- Paired-file translation, non-project report roots, exhaustive report schemas, diagnostic-mode outputs, retry/resume matrices, and governance-grade provenance are post-MVP unless explicitly promoted by the HLD.

All MVP YAML/JSON project artifacts and report envelopes defined by this spec MUST use `schema_version: "1.0"` or `"schema_version": "1.0"` as appropriate for their file format. This requirement does not apply to `translation-memory.sqlite`; translation-memory schema versioning and metadata (if any) are owned by the Translation Memory Specification.

## 2. Artifact Authority and Ownership

The MVP artifact set is intentionally small. Each artifact has one authoritative producer and a narrow mutation surface.

| Artifact | Format | Location | Authority / producer | Allowed mutators | Detailed contract owner |
| --- | --- | --- | --- | --- | --- |
| Project manifest | YAML | `<project-root>/parley.yaml` | Project Service via CLI | Project Service | This spec |
| Localization inventory | YAML | `<project-root>/inventory.yaml` | Inventory Service | Inventory Service | This spec |
| Canonical inventory | JSON | `<project-root>/canonical-inventory.json` | Canonical Inventory Service | Canonical Inventory Service | This spec |
| Context anchor | YAML | `<project-root>/context-anchor.yaml` | Context Anchor Service | Context Anchor Service; explicit human review flow | This spec + Confidence Model Specification |
| Glossary | YAML | `<project-root>/glossary.yaml` (optional physical file; see Section 8) | Human-authored terminology workflow | Humans or explicit glossary commands | This spec + Validation and Error Taxonomy Specification |
| Translation memory | SQLite | `<project-root>/translation-memory.sqlite` | Translation Memory Service | Translation Memory Service | Translation Memory Specification |
| Reports | JSON | `<project-root>/reports/<report-family>/` | Report Writer invoked by Project Service | Report Writer | This spec + command specs + Validation and Error Taxonomy Specification |

Requiredness model note (MVP): `parley.yaml` MUST include the `artifacts.glossary` manifest pointer, but the `glossary.yaml` file itself MAY be absent. If `glossary.yaml` is absent, glossary evaluation behaves as if an empty ruleset is present; if it is present, it MUST be schema-valid.

The Project Artifact Schema Specification owns the enclosing schema and placement of these artifacts. It does not own:

- Parser-specific normalized entry contracts, placeholder parsing, or write-back formatting; those are owned by the Parser Interface and Format Specification.
- Validation finding categories, severities, canonical finding IDs, finding shape, or finding ordering; those are owned by the Validation and Error Taxonomy Specification.
- Confidence scoring semantics and dimension meanings; those are owned by the Confidence Model Specification.
- Translation-memory table schema, record identity, and current-record mutation semantics; those are owned by the Translation Memory Specification.

## 3. Shared Types and Conventions

| Type | Definition |
| --- | --- |
| `ID` | Lowercase string matching `^[a-z0-9][a-z0-9._-]*$`. |
| `Locale` | BCP 47 locale string, such as `en-US` or `fr-FR`. |
| `Timestamp` | UTC RFC 3339 timestamp. Unless a leaf command spec states otherwise, timestamps persisted by artifacts and report envelopes defined in this spec MUST be serialized as whole-second UTC RFC 3339 with an explicit `Z` suffix. If a command spec requires a different precision, it MUST still be UTC RFC 3339 and MUST be deterministic. |
| `Hash` | Lowercase SHA-256 hex digest. |
| `RelativePath` | Canonical project-root-relative path string. Absolute paths MUST NOT be stored in project artifacts or completed reports. |
| `ReportFamily` | One of `initialization`, `validation`, `confidence`, `translation`, `comparison`, or `translation_memory`. |

### 3.1 RelativePath Normalization

MVP `RelativePath` fields use one canonical serialized form:

- `/` is the only allowed separator.
- The path MUST NOT be empty after normalization.
- The path MUST NOT be `.`.
- The path MUST NOT start with `/`.
- The path MUST NOT contain `\`.
- The path MUST NOT contain a Windows drive prefix or UNC prefix.
- Parent traversal (`..`) is not allowed.

Normalization for user input prior to persistence:

1. Reject the path if the raw input starts with `/` (absolute path, including UNC-style `//` prefixes).
2. Reject the path if the raw input contains `\`.
3. Reject the path if the raw input matches a Windows drive prefix (`^[A-Za-z]:`).
4. Split the input on `/`.
5. Drop empty and `.` segments.
6. Reject the path if any segment is `..`.
7. Join retained segments with `/`.
8. Reject the path if the result is empty.

Fields typed as `RelativePath` MUST be persisted in this canonical serialized form. Validators MUST treat non-canonical stored values as artifact schema errors.

Common enums:

| Enum | Values |
| --- | --- |
| Localization format | `ios_strings`, `android_xml` |
| Localization role | `authoritative`, `target` |
| Human status | `draft`, `reviewed`, `approved`, `locked` |
| Context source | `machine`, `human`, `imported` |

Unless a more specific leaf spec states otherwise, hashes MUST be SHA-256 over canonical JSON:

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

For canonical inventory entries, `content_hash` MUST be computed over the canonical JSON object containing:

- `key`: the canonical entry `key`
- `value`: the canonical entry `authoritative_value`
- `locale`: `canonical-inventory.authoritative_locale`
- `format`: `canonical-inventory.authoritative_format`
- `placeholder_signature`: the canonical entry `placeholder_signature`

`value_hash` for canonical inventory entries MUST be computed as SHA-256 over the UTF-8 bytes of the decoded `authoritative_value` string exactly as stored, with no additional Unicode normalization, newline normalization, or trimming.

`inventory_hash` for `canonical-inventory.json` MUST be computed as SHA-256 over the canonical JSON serialization of this object:

- `authoritative_locale`: the canonical inventory `authoritative_locale`
- `authoritative_format`: the canonical inventory `authoritative_format`
- `entries`: an object keyed by canonical localization key, where each value contains:
  - `authoritative_value`
  - `placeholder_signature`

The `inventory_hash` input MUST NOT include timestamps, report metadata, `first_seen_at`, `last_updated_at`, parser diagnostics, or non-semantic metadata.

## 4. `parley.yaml`

`parley.yaml` is the human-readable project manifest.

Required fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project.id` | `ID` | Stable project ID. |
| `project.name` | string | Human-readable project name. |
| `project.authoritative_localization_id` | `ID` | `inventory.yaml` localization ID for the authoritative localization. |
| `project.authoritative_locale` | `Locale` | Source locale used as the semantic baseline. |
| `artifacts.inventory` | `RelativePath` | Path to `inventory.yaml`; normally `inventory.yaml`. |
| `artifacts.canonical_inventory` | `RelativePath` | Path to `canonical-inventory.json`; normally `canonical-inventory.json`. |
| `artifacts.context_anchor` | `RelativePath` | Path to `context-anchor.yaml`; normally `context-anchor.yaml`. |
| `artifacts.glossary` | `RelativePath` | Path to `glossary.yaml`; normally `glossary.yaml`. This manifest pointer is required even though the file may be absent. |
| `artifacts.translation_memory` | `RelativePath` | Path to `translation-memory.sqlite`; normally `translation-memory.sqlite`. |

Optional MVP fields:

| Field | Type | Description |
| --- | --- | --- |
| `project.description` | string | Project-level context seed. |
| `defaults.provider` | string | Default provider adapter ID. |
| `defaults.report_format` | string | If present, MUST be `json` for the MVP. |

Validation policy may be represented in `parley.yaml`, but this spec does not define a comprehensive policy matrix for the MVP. If present, policy fields MUST NOT override the exit-code precedence defined by the CLI Command Specification or the category/severity rules defined by the Validation and Error Taxonomy Specification.

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
```

## 5. `inventory.yaml`

`inventory.yaml` lists project-managed localization files.

Required top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project_id` | `ID` | Project ID from `parley.yaml`. |
| `localizations` | array | Localization file records. |

Localization record:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `localization_id` | `ID` | yes | Stable localization ID referenced by project and reports. |
| `locale` | `Locale` | yes | File locale. |
| `format` | enum | yes | `ios_strings` or `android_xml`. |
| `path` | `RelativePath` | yes | File path relative to project root. |
| `role` | enum | yes | `authoritative` or `target`. |
| `status` | enum | yes | `draft`, `reviewed`, `approved`, or `locked`. |
| `parser` | string | yes | Parser adapter ID. |
| `last_observed_hash` | `Hash` | no | Hash of the last normalized parsed file observed by Parley. |
| `last_validated_at` | `Timestamp` | no | Last completed validation timestamp for this record. |

Rules:

- Exactly one localization record MUST have `role: authoritative`.
- `project.authoritative_localization_id` in `parley.yaml` MUST match that authoritative record's `localization_id`.
- `path` values MUST be valid `RelativePath` values in canonical serialized form and unique within the inventory.
- `localization_id` values MUST be unique within the inventory.
- The inventory is not the source of parser grammar or normalized entry shape; parser details are owned by the Parser Interface and Format Specification.

## 6. `canonical-inventory.json`

`canonical-inventory.json` is a machine-managed baseline derived from the authoritative localization.

Required top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project_id` | `ID` | Project ID from `parley.yaml`. |
| `authoritative_localization_id` | `ID` | Authoritative inventory localization ID. |
| `authoritative_locale` | `Locale` | Source locale. |
| `authoritative_format` | enum | Authoritative localization format: `ios_strings` or `android_xml`. |
| `generated_at` | `Timestamp` | Timestamp for the generation run. |
| `inventory_hash` | `Hash` | Hash of the authoritative parsed localization baseline used to generate this artifact. |
| `entries` | object | Map from canonical localization key to canonical entry. |

Canonical entry:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | yes | Localization key. MUST equal the map key. |
| `authoritative_value` | string | yes | Source value. |
| `value_hash` | `Hash` | yes | Hash of authoritative value. |
| `content_hash` | `Hash` | yes | Entry content hash as defined by this spec. |
| `placeholder_signature` | string | yes | Normalized placeholder signature. |
| `placeholders` | array | yes | Placeholder token records from the parser layer. |
| `first_seen_at` | `Timestamp` | yes | First canonical inventory observation. |
| `last_updated_at` | `Timestamp` | yes | Last canonical value change. |

Rules:

- Canonical inventory key order for reports and translation workflows is lexical order of `entries` map keys unless a command spec defines a more specific stable order.
- Canonical inventory is generated from the authoritative localization only. Target localization files MUST NOT mutate it.
- For each canonical entry, `value_hash` and `content_hash` MUST be computed by the rules in Section 3.
- Placeholder record details are owned by the Parser Interface and Format Specification and Placeholder Token Integrity Specification.

Timestamp mutation semantics (MVP):

- `generated_at` is volatile run metadata. It MAY change on every regeneration and MUST NOT be treated as semantic comparison material for the canonical inventory.
- `first_seen_at` MUST be set when a canonical entry key is first introduced into the canonical inventory and MUST NOT change on later regenerations if that key remains present.
- `last_updated_at` MUST be updated only when the entry's deterministic content changes. If `content_hash` is unchanged, `last_updated_at` MUST remain unchanged.
- If `canonical-inventory.json` already exists, the canonical inventory writer MUST preserve existing `first_seen_at` and `last_updated_at` values for keys whose deterministic content has not changed.

## 7. `context-anchor.yaml`

`context-anchor.yaml` stores project-level and per-key context. It may be created by `parley project init` as a schema-valid empty placeholder without provider calls.

Required top-level fields:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project_id` | `ID` | Project ID from `parley.yaml`. |
| `authoritative_locale` | `Locale` | Source locale used for context. |
| `project_context.description` | string | Project-level context. MAY be empty when created by `parley project init`. |
| `entries` | object | Map from localization key to context entry. MAY be empty for the initial placeholder. |

Optional project context fields:

| Field | Type | Description |
| --- | --- |
| `project_context.domain` | string | Functional domain. |
| `project_context.considerations` | array of strings | Translation considerations. |

Context entry:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `key` | string | yes | Localization key. MUST equal the map key. |
| `context_description` | string | yes | Intended usage or meaning. |
| `human_status` | enum | yes | `draft`, `reviewed`, `approved`, or `locked`. |
| `source` | enum | yes | `machine`, `human`, or `imported`. |
| `updated_at` | `Timestamp` | yes | Last update time for this entry. |
| `notes` | string | no | Optional reviewer notes. |
| `confidence` | object | no | Optional confidence metadata; semantics are owned by the Confidence Model Specification. |

Rules:

- A schema-valid empty context anchor is acceptable for project initialization and some confidence workflows.
- Project-mode translation requires populated per-key context as defined by the CLI Command Specification; this spec only defines how the context is stored.
- Confidence dimensions, score meanings, and confidence report behavior are owned by the Confidence Model Specification.
- `updated_at` is a mutation timestamp, not a regeneration timestamp: it MUST be updated only when the context entry's stored content changes. Pure reserialization, reordering, or an identical rewrite MUST NOT bump `updated_at`.

## 8. `glossary.yaml`

`glossary.yaml` stores human-authored terminology rules. For the MVP, `glossary.yaml` is an optional project artifact; if absent, glossary evaluation behaves as if an empty ruleset is present.

Project initialization rules:

- `parley project init` MAY create a schema-valid `glossary.yaml` placeholder with `rules: []`.
- If `glossary.yaml` is missing, project validation MUST NOT fail due to glossary absence.
- If `glossary.yaml` is present, it MUST be schema-valid.

Required top-level fields when present:

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | MUST be `"1.0"`. |
| `project_id` | `ID` | Project ID from `parley.yaml`. |
| `glossary_version` | `ID` | Stable glossary version. |
| `rules` | array | Glossary rules. MAY be empty. |

Glossary rule:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | `ID` | yes | Rule ID. |
| `term` | string | yes | Source term or phrase. |
| `type` | enum | yes | `preferred`, `prohibited`, `protected`, `untranslated`, or `canonical`. |
| `source_locale` | `Locale` | no | Locale for source term. |
| `target_locale` | `Locale` or `*` | no | Target locale scope. |
| `translation` | string | no | Required or preferred target text. |
| `case_sensitive` | boolean | no | Defaults to `false`. |
| `severity` | enum | no | Validation severity. When present, it MUST be one of `info`, `warning`, `error`, or `blocking`. Category/severity semantics are owned by the Validation and Error Taxonomy Specification. |
| `notes` | string | no | Human notes. |

Severity values (MVP):

- `info`
- `warning`
- `error`
- `blocking`

Rule evaluation order, terminology finding categories, and severity promotion are owned by the Validation and Error Taxonomy Specification unless a glossary-specific leaf spec is introduced.

## 9. MVP Report Placement and Envelope

MVP reports are project-scoped artifacts.

Report placement:

- The default report root is `<project-root>/reports/`.
- A command may accept `--report-dir`. For the MVP, `--report-dir` MUST resolve as a `RelativePath` under `<project-root>/reports/`.
  - If `--report-dir` is omitted, `<resolved-report-dir>` is `<project-root>/reports/`.
  - If `--report-dir` is present, `<resolved-report-dir>` is `<project-root>/reports/<normalized --report-dir>/`.
- Report files MUST be written under a report-family subdirectory rooted at `<resolved-report-dir>`:
  - `<resolved-report-dir>/initialization/`
  - `<resolved-report-dir>/validation/`
  - `<resolved-report-dir>/confidence/`
  - `<resolved-report-dir>/translation/`
  - `<resolved-report-dir>/comparison/`
  - `<resolved-report-dir>/translation_memory/`
- Report file naming MUST be deterministic for an invocation:
  - The command MUST provide a `run_id` string in the report envelope.
  - `run_id_filename` is `run_id` with every character not in `[A-Za-z0-9._-]` replaced with `_`.
  - `run_id_filename` MUST NOT be empty after this transformation.
  - The full report path MUST be `<resolved-report-dir>/<report_family>/<run_id_filename>.json`.
- Commands MUST NOT silently overwrite an existing report file. If the computed report file path already exists and the command invocation does not include an explicit command-owned overwrite option that defines overwrite semantics, the command MUST treat this as an IO failure and MUST NOT modify the existing file.

Report determinism and comparison:

- `run_id`, `started_at`, and `created_at` are volatile invocation metadata. They MUST be present in the report envelope, but MUST NOT be treated as semantic comparison material when comparing report meaning across runs or implementations.
- `run_id` MUST be supplied by the command layer and MUST be stable within one invocation. It MAY be non-deterministic across separate invocations. Reproducible replay identifiers are post-MVP.
- JSON object keys in completed reports MUST use canonical JSON key ordering as defined in Section 3 when serialized for deterministic comparison.
- If a command emits repeated arrays in report payloads, the command spec or owning leaf spec MUST define stable emission order for those arrays. For validation/comparison `findings`, the stable order and ID derivation are owned by the Validation and Error Taxonomy Specification.

For the MVP, this spec uses `report_family` to mean the `ReportFamily` enum. Any finer-grained subtype distinctions are command-spec-owned and post-MVP unless explicitly promoted.

Common report envelope:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `schema_version` | string | yes | MUST be `"1.0"`. |
| `report_family` | `ReportFamily` | yes | Report family. |
| `run_id` | string | yes | Unique invocation ID. |
| `project_id` | `ID` | yes | Project ID. Null project IDs are not part of the MVP report surface. |
| `command` | string | yes | CLI command name. |
| `started_at` | `Timestamp` | yes | Command invocation start timestamp. |
| `created_at` | `Timestamp` | yes | Report creation timestamp. |
| `inputs` | object | yes | Minimal command-specific input summary. |
| `summary` | object | yes | Minimal aggregate summary. MAY be empty when the command spec does not require counts. |

Optional common envelope fields:

| Field | Type | Description |
| --- | --- |
| `provider_status` | string | Provider status when a command invokes or classifies provider-backed work. |
| `provider` | object | Provider metadata when provider-backed work is used or explicitly classified. |
| `failure_category` | `FailureCategory` | Shared failure category when the command exits unsuccessfully and a report is written (see Section 9.1). |
| `findings` | array | Validation/comparison findings. Finding shape, stable finding IDs, and finding order are owned by the Validation and Error Taxonomy Specification. |

### 9.1 `failure_category` (MVP)

The common report envelope `failure_category` is a minimal, shared MVP vocabulary for obvious unsuccessful outcomes. It intentionally does not define an exhaustive error-code registry.

Rules:

- `failure_category` MUST be omitted when a command exits successfully (CLI exit code `0`).
- If a command writes a completed report and exits unsuccessfully (non-zero exit code), `failure_category` MUST be present and MUST be one of the values in the enum below.
- `failure_category` MUST be consistent with the CLI exit-code class for the invocation (see mapping guidance below). Command specs MAY define additional command-specific fields that further qualify the failure without expanding this shared enum.

`FailureCategory` enum (MVP):

| Value | Meaning |
| --- | --- |
| `artifact_schema` | An artifact schema error prevented correct execution (including invalid `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, `glossary.yaml` when present, or a schema-invalid report envelope/payload where applicable). |
| `precondition_failed` | Usage/configuration/environment preconditions were not met (e.g., missing required arguments, missing required files, disallowed state) and the command could not proceed. |
| `io` | File system IO failure (including inability to read inputs or inability to write the report file per the deterministic path rules). |
| `parser` | Parser or file-format parse failure while reading localization files (distinct from generic IO). |
| `provider` | A required provider operation failed or a required provider was unavailable. |
| `blocking_validation` | The command completed but produced blocking findings that cause an unsuccessful outcome for the invocation. |

Exit-code consistency guidance (MVP):

- Exit code `1` (blocking findings): `failure_category` MUST be `blocking_validation`.
- Exit code `4` (required provider operation failed): `failure_category` MUST be `provider`.
- Exit code `3` (parser or file IO failure): `failure_category` MUST be `parser` when the primary failure is parsing/decoding/format interpretation; otherwise it MUST be `io`.
- Exit code `2` (usage, configuration, or artifact schema error): `failure_category` MUST be `artifact_schema` when the primary failure is an artifact schema error; otherwise it MUST be `precondition_failed`.

Command-specific report fields are owned by command specs. Examples include `validated_localizations` for validation reports and `per_key_outcomes` for translation reports. This spec intentionally does not define exhaustive report schemas for the MVP.

## 10. Translation Memory Artifact Boundary

`translation-memory.sqlite` is a required project artifact for MVP translation workflows, but this spec does not define its internal database schema.

Rules:

- `parley.yaml` names the translation-memory path.
- Commands that require translation memory MUST validate that the file exists and satisfies the Translation Memory Specification before using it.
- Translation-memory record fields, record identity, current-record conflict behavior, import/export formats, and write-back semantics are owned by the Translation Memory Specification.
- JSONL translation-memory import/export is post-MVP surface for this spec; when implemented, it MUST be consistent with the Translation Memory Specification rather than duplicating a competing schema here.
