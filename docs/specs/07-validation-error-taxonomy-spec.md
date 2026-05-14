# Validation and Error Taxonomy Specification

## 1. Scope

This specification defines canonical validation categories, severity levels, finding shape, CI policy mapping, examples, and exit code interaction.

It is the authority for the finding `category` and `severity` enums and the MVP finding object shape used inside Parley validation reports. The Project Artifact Schema Specification is the authority for the enclosing validation report document schema (report roots, run metadata, and any report-level structure around findings).

For the MVP, validation reports that carry these findings are **project-scoped** artifacts under `<project-root>/reports/` as defined by the Parley High-Level Design (HLD) and the Project Artifact Schema Specification. Non-project report roots and paired-file translation report placement are post-MVP unless explicitly promoted.

Architecture authority for MVP boundaries is the Parley High-Level Design (HLD). The v1 spec index is dependency/navigation context only.

## 2. Severity Levels

| Severity | Meaning |
| --- | --- |
| `info` | Informational note; no quality risk by itself. |
| `warning` | Potential issue; should be reviewed. |
| `error` | Defect likely needing correction, but command may continue. |
| `blocking` | Defect that must block write, release, or CI success. |

Absent CI policy evaluation, only findings with severity `blocking` force CLI exit code `1` when the command otherwise completed. After policy evaluation, findings promoted to blocking for CI/exit-code purposes also cause exit code `1` without mutating their original `severity`.

## 3. Finding Categories

| Category | Description |
| --- | --- |
| `structural` | Missing keys, extra keys, duplicate keys, inventory/key baseline mismatches. |
| `parser_syntax` | Parser diagnostics for inputs that were read but contain syntax that cannot be parsed cleanly according to the parser grammar. If the required report can still be produced, fatal syntax diagnostics MUST be emitted as `parser_syntax` findings; only failures that prevent producing the required report are process failures (Section 7). |
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

This spec owns the canonical finding object shape (fields and constraints), category enum, severity enum, default severity mapping, policy promotion behavior, and exit-code interaction. The Project Artifact Schema Specification owns the enclosing validation report document schema that carries findings.

### 4.1 Required Fields (MVP)

For the MVP, report producers MUST emit at least the following finding fields, with the given constraints:

| Field | Type | Required | Nullable | Constraints / Notes |
| --- | --- | --- | --- | --- |
| `id` | string | MUST | MUST NOT | Deterministic for the same normalized finding inputs; opaque to consumers. |
| `category` | string | MUST | MUST NOT | One of the categories in Section 3. |
| `severity` | string | MUST | MUST NOT | One of the severities in Section 2. This is the *original* severity prior to policy evaluation. |
| `message` | string | MUST | MUST NOT | Human-readable explanation of the finding. |
| `origin` | string | MUST | MUST NOT | One of: `machine`, `human`. |
| `policy_blocked` | boolean | MAY | MUST NOT | Optional annotation. If `true`, indicates the finding is treated as blocking for CI/exit-code purposes due to policy (Section 6), without mutating `severity`. |

Determinism requirements (MVP):

**Canonical finding ID**

- Producers MUST compute `id` from a canonical ID input record with exactly these keys: `category`, `check_id`, `file`, `locale`, `key`.
- `message` MUST NOT be included in finding identity. Human-readable wording may change without changing the underlying condition.
- For each key, the normalized value is:
  - If the source value is unknown or not applicable: `null`.
  - Otherwise a string normalized by: (1) Unicode NFC, (2) convert CRLF and CR to LF, (3) trim leading/trailing whitespace.
- `file` source and normalization (MVP):
  - If the finding is scoped to a project-managed file listed in the project's localization inventory, `file` MUST be the inventory record's project-root-relative path.
  - Otherwise, if the finding is scoped to a file under the project root but not present in the inventory, `file` MUST be the project-root-relative path.
  - Otherwise, `file` MUST be `null`.
  - In all cases where `file` is non-`null`, it MUST use forward slashes (`/`) and MUST NOT contain a leading `./`.
  - Absolute paths MUST NOT appear in completed reports and MUST NOT be used for canonical ID computation.
- `check_id` is an opaque rule/check identifier string.
  - If no rule/check exists, set `check_id` to `null` (not an empty string).
  - For the default MVP conditions in Section 5, producers MUST use the canonical `check_id` values defined below.
  - If `check_id` is non-`null` in the canonical ID input, producers MUST also emit the same value as a top-level `check_id` field on the finding so the `id` can be reproduced from report content.
- Canonical ID input visibility rule (MVP):
  - For each of `check_id`, `file`, `locale`, and `key`: if the canonical ID input normalized value is non-`null`, the producer MUST emit the corresponding top-level finding field with the same normalized string value.
  - Conversely, if the producer omits any of those top-level fields, the canonical ID input normalized value for that key MUST be `null`.

Canonical `check_id` values for default MVP conditions:

| Condition (Section 5) | Canonical `check_id` |
| --- | --- |
| Missing key relative to canonical inventory | `structural_missing_key` |
| Extra key not in canonical inventory | `structural_extra_key` |
| Duplicate key | `structural_duplicate_key` |
| Fatal parser syntax issue | `parser_syntax_fatal` |
| Recoverable parser syntax issue | `parser_syntax_recoverable` |
| Localization syntax violation | `localization_syntax_violation` |
| Missing placeholder | `placeholder_missing` |
| Placeholder type mismatch | `placeholder_type_mismatch` |
| Invalid placeholder reorder | `placeholder_reorder_invalid` |
| Glossary prohibited term used | `terminology_glossary_prohibited_term` |
| Protected product name translated | `terminology_protected_product_name_translated` |
| Spelling issue | `spelling_issue` |
| Grammar issue | `grammar_issue` |
| Clarity issue | `clarity_issue` |
| Meaning drift from authoritative baseline | `semantic_meaning_drift` |
| Severe mistranslation | `semantic_severe_mistranslation` |
| Reportable artifact schema violation | `artifact_schema_violation` |
| Reportable IO warning (report completed) | `io_warning` |
| Reportable IO error (report completed) | `io_error` |
| Provider warning (reportable; report completed) | `provider_warning` |
| Provider error (reportable; report completed) | `provider_error` |

Canonical JSON serialization (normative):

- The canonical ID input record MUST be serialized as a JSON object with **exactly** the five keys above, each present exactly once with a value that is either `null` or a JSON string.
- Object members MUST appear in lexicographic ascending order by Unicode codepoint over the key strings. For these keys, the required order is:
  1) `category`
  2) `check_id`
  3) `file`
  4) `key`
  5) `locale`
- The serialization MUST contain no insignificant whitespace (no spaces, tabs, or newlines).
- Strings MUST be encoded as JSON strings using:
  - UTF-8 for the underlying bytes.
  - Quotation mark U+0022 MUST be escaped as `\"` and reverse solidus U+005C MUST be escaped as `\\`.
  - Control characters U+0000 through U+001F MUST be escaped as `\u00xx` with **lowercase** hex digits.
  - U+2028 and U+2029 MUST be escaped as `\u2028` and `\u2029`.
  - All other Unicode characters MUST be emitted as their UTF-8 bytes (i.e., MUST NOT be escaped as `\uXXXX`).
- `null` MUST be serialized as the literal `null`.

ID digest construction (normative):

- The canonical ID bytes are the UTF-8 bytes of the canonical JSON serialization defined above.
- The finding `id` MUST be computed as: `"sha256:" + LOWERCASE_HEX(SHA-256(canonical_id_bytes))`.

Multiplicity / aggregation rule (MVP):

- Producers MUST NOT emit more than one finding with the same canonical ID input record (same normalized values for `category`, `check_id`, `file`, `locale`, `key`).
- If multiple distinct underlying observations map to the same canonical ID input record, producers MUST aggregate them into a single finding.
  - Producers MAY include per-occurrence details (locations, spans, excerpts, subconditions) in `rationale` and/or `suggested_fix`.
  - If per-occurrence details are included, producers MUST make them deterministic by sorting them (ascending) using the same string normalization rules as the canonical finding ID.

Canonical finding order (for deterministic report output):

- Producers MUST sort findings using the following canonical sort key tuple:
  1) `category` (ascending, by Unicode codepoint order of the normalized string)
  2) `severity_rank` (descending), where the rank order is `blocking` > `error` > `warning` > `info`
  3) `file` (ascending)
  4) `locale` (ascending)
  5) `key` (ascending)
  6) `id` (ascending; final tie-breaker)
- For ordering comparisons, each of `file`, `locale`, and `key` MUST use the same normalization rules as the canonical finding ID. If a value is `null`, it MUST sort after any non-`null` value for that field.

The following fields are RECOMMENDED when known but MAY be omitted when not applicable (except as constrained above for canonical ID inputs): `check_id` (string), `locale` (string), `file` (string), `key` (string), `rationale` (string), `suggested_fix` (string).

```json
{
  "id": "sha256:f12e3a5e1b23cc2101f5073512ba480f67f46804912d2ff9f409c1412e2d1a27",
  "category": "placeholder_integrity",
  "severity": "blocking",
  "check_id": "placeholder_missing",
  "locale": "fr-FR",
  "file": "fr.lproj/Localizable.strings",
  "key": "welcome_message",
  "message": "Missing placeholder {name}արդ.",
  "rationale": "The authoritative string contains {name}, but the target string does not.",
  "suggested_fix": "Restore {name} in the translated string.",
  "origin": "machine"
}
```

## 5. Default Severity Mapping

In this table, a "fatal" parser syntax issue is a reportable finding when the required report can still be produced (Section 7); otherwise it is a process failure.

Provider warnings/errors are reportable findings when the required report can still be produced (Section 7); if a required provider operation prevents producing the required report, the command terminates with exit code `4`.

| Condition | Category | Severity |
| --- | --- | --- |
| Missing key relative to canonical inventory | `structural` | `blocking` |
| Extra key not in canonical inventory | `structural` | `warning` |
| Duplicate key | `structural` | `blocking` |
| Fatal parser syntax issue | `parser_syntax` | `blocking` |
| Recoverable parser syntax issue | `parser_syntax` | `error` |
| Localization syntax violation | `localization_syntax` | `error` |
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
| Reportable IO warning (report completed) | `io` | `warning` |
| Reportable IO error (report completed) | `io` | `error` |
| Provider warning (reportable; report completed) | `provider` | `warning` |
| Provider error (reportable; report completed) | `provider` | `error` |

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

If omitted, `blocking_categories` defaults to `[]` and `blocking_severities` defaults to [`blocking`].

Rules:

- Any finding whose severity is `blocking` is blocking.
- Any finding whose severity is listed in `blocking_severities` is treated as blocking for CI/exit-code purposes.
- Any finding whose category is listed in `blocking_categories` is treated as blocking for CI/exit-code purposes.
- Policy promotion MUST NOT mutate the original finding `severity`.
- If a non-`blocking` finding is treated as blocking due to policy, reports SHOULD include `policy_blocked: true` on that finding.

## 7. Exit Code Interaction

Deterministic boundary rule (MVP):

- If validation **completes** and a report is produced, all detectable validation issues MUST be represented as findings in that report (including `artifact_schema` when applicable), and exit codes follow the completed-validation rules (`0`/`1`) after policy evaluation.
- If an artifact schema problem prevents command startup or prevents producing the required report artifact, the command MUST exit `2`.
- If a required input cannot be read/normalized, a required project/report context cannot be loaded, or the required report artifact cannot be written, the command MUST terminate as a process failure with exit code `3`.

Parser/IO classification rule (MVP):

- If the required report can be produced, then syntax diagnostics for readable inputs MUST be emitted as `parser_syntax` findings (using the `parser_syntax_fatal` or `parser_syntax_recoverable` check IDs as appropriate) rather than causing exit `3`.
- If the required report can be produced, then IO/path issues that are detected but do not prevent producing the required report artifact MUST be emitted as `io` findings (using `io_warning` / `io_error` as applicable) rather than causing exit `3`.
- Exit `3` is reserved for failures that prevent producing the required report artifact (for example: required bytes cannot be read at all, required project/report roots cannot be resolved, or the report cannot be written).

Provider classification rule (MVP):

- Provider-backed operations are optional unless a command explicitly enables or requires them.
- If the required report can be produced, provider warnings/errors that are available MUST be emitted as `provider` findings (using `provider_warning` / `provider_error` as applicable) rather than causing exit `4`.
- Exit `4` is reserved for failures of a **required** provider operation that prevent producing the required report artifact (process failure; report not completed).

| Scenario | Exit code |
| --- | --- |
| Validation completed and no blocking findings after policy | `0` |
| Validation completed with blocking findings after policy | `1` |
| Invalid CLI options, invalid configuration, or artifact schema error that prevents command startup or required report production | `2` |
| Required input cannot be read or required report cannot be written (process failure; report not completed) | `3` |
| Required provider operation fails and prevents producing the required report (process failure; report not completed) | `4` |

If a command explicitly validates artifacts and can produce a report, it MUST include `artifact_schema` findings when applicable; blocking findings in that completed report use exit code `1`.

## 8. Examples

Note: The `id` values in the examples below are illustrative placeholders. In completed reports, the `id` MUST be computed from the canonical ID input record defined in Section 4.1. The examples include the relevant canonical-ID input fields (`check_id`, `file`, `locale`, `key`) as top-level finding fields when they are non-`null`.

Missing canonical key:

```json
{
  "id": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "category": "structural",
  "severity": "blocking",
  "check_id": "structural_missing_key",
  "locale": "fr-FR",
  "file": "fr.lproj/Localizable.strings",
  "key": "ok_button",
  "message": "Target localization is missing key ok_button.",
  "origin": "machine"
}
```

Terminology violation:

```json
{
  "id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  "category": "terminology",
  "severity": "error",
  "check_id": "terminology_glossary_prohibited_term",
  "locale": "fr-FR",
  "file": "fr.lproj/Localizable.strings",
  "key": "account_label",
  "message": "Preferred translation for Account is Compte.",
  "origin": "machine"
}
```

Semantic drift:

```json
{
  "id": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "category": "semantic",
  "severity": "error",
  "check_id": "semantic_meaning_drift",
  "locale": "fr-FR",
  "file": "fr.lproj/Localizable.strings",
  "key": "confirm_button",
  "message": "Target text changes the meaning from confirmation to cancellation.",
  "origin": "machine"
}
```