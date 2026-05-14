# Confidence Model Specification

## 1. Scope

This specification defines confidence dimensions, score ranges, aggregation rules, human confirmation states, confidence report artifact behavior (minimal MVP contract), confidence report entries, and thresholds used by project-first translation workflows.

Architecture authority:

- The architecture HLD is the authority for project-first workflow ordering, report rooting, run scoping, and provider-optional behavior.

Dependencies (leaf specs):

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Translation Workflow Specification](06-translation-workflow-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

Dependency/navigation context:

- The spec index (`00-spec-index.md`) is navigation/dependency context only; it is not authority over the HLD.

Out of scope / deferred surfaces (not expanded here):

- Paired-file (non-project) translation and non-project report roots.
- Exhaustive report schemas and full validation matrices.

## 2. Confidence Dimensions

All confidence records MUST use these dimensions:

| Dimension | Meaning |
| --- | --- |
| `semantic` | Confidence that source and target preserve intended meaning. |
| `contextual` | Confidence that project and per-string context are understood. |
| `grammatical` | Confidence in grammar and language naturalness. |
| `terminology_compliance` | Confidence that glossary rules are followed. |
| `placeholder_integrity` | Confidence that placeholders/tokens are preserved correctly. |
| `clarity` | Confidence that the string is clear for intended users. |

Scores MUST be numbers from `0.0` to `1.0`.

## 3. Confidence Object

A confidence object represents per-dimension scores plus an aggregate.

```json
{
  "dimensions": {
    "semantic": 0.92,
    "contextual": 0.88,
    "grammatical": 0.95,
    "terminology_compliance": 0.9,
    "placeholder_integrity": 1.0,
    "clarity": 0.91
  },
  "aggregate": 0.92,
  "method": "provider_assessed",
  "origin": "machine",
  "assessed_at": "2026-05-08T00:00:00Z"
}
```

### 3.1 Schema and validation (MVP)

When a confidence object is present (for example in confidence report entries for `standalone` or `relative_to_anchor`), it MUST conform to the schema below.

| Field | Type | Required? | Nullable? | Rules |
| --- | --- | --- | --- | --- |
| `dimensions` | object | required | not null | MUST include all six dimensions in section 2 and MUST NOT include other dimension keys; each value MUST be a number in `[0.0, 1.0]`. |
| `aggregate` | number | required | not null | MUST be a number in `[0.0, 1.0]` AND MUST equal the deterministic aggregate defined in section 4.2 for the same `dimensions` (regardless of `method`). If a producer needs to preserve a provider-supplied or imported aggregate that does not equal the section 4.2 value, it MUST be carried in an additional producer-defined field (e.g., `source_aggregate`) and MUST NOT be used for thresholds. |
| `method` | string | required | not null | One of `deterministic`, `provider_assessed`, `human_confirmed`, `imported`. |
| `origin` | string | required | not null | One of `machine`, `human`, `provider`, `imported`. |
| `assessed_at` | string | required | not null | RFC3339 timestamp (e.g., `2026-05-08T00:00:00Z`). |

Forward-compatibility:

- Producers MAY include additional fields in the confidence object.
- MVP consumers MUST ignore unknown fields when parsing/validating confidence objects.

`method` values:

- `deterministic`
- `provider_assessed`
- `human_confirmed`
- `imported`

`origin` values:

- `machine`
- `human`
- `provider`
- `imported`

## 4. Aggregation

Default aggregate confidence MUST use weighted average:

| Dimension | Weight |
| --- | --- |
| `semantic` | `0.25` |
| `contextual` | `0.25` |
| `grammatical` | `0.15` |
| `terminology_compliance` | `0.15` |
| `placeholder_integrity` | `0.10` |
| `clarity` | `0.10` |

### 4.1 Requiredness and input validation

- All six dimensions in section 2 are required.
- If any required dimension is missing, the confidence object is invalid and artifact validation MUST fail with exit code `2`.
- Each dimension score MUST be a number in `[0.0, 1.0]`.

If validation emits a `blocking` finding for `placeholder_integrity`, the `placeholder_integrity` confidence MUST be `0.0`.

### 4.2 Deterministic aggregate computation (MVP)

Definitions:

- Let `s[d]` be the score for dimension `d`.
- Let `w[d]` be the weight for dimension `d`.

Numeric computation model (MVP):

- For deterministic computation, implementations MUST treat all confidence scores and weights as **exact base-10 decimal values** (not binary floating point approximations).
- When parsing JSON, implementations MUST parse numeric tokens into an exact decimal representation (e.g., arbitrary-precision decimal or fixed-point) so that independent implementations produce identical `raw`, rounding ties, and threshold outcomes.
  - Implementations MUST NOT compute `raw` or perform threshold comparisons using IEEE-754 binary floating point unless they first convert to an exact-decimal or fixed-point representation that preserves the intended numeric value.

Algorithm:

1. Compute `raw = sum(w[d] * s[d])` over the six required dimensions using exact-decimal or fixed-point arithmetic, with **no intermediate rounding**.
2. Compute `aggregate = round(raw, 2)` where `round(x, 2)` rounds to two decimal places using round-half-up (ties go away from zero).
   - Because `raw` is always in `[0.0, 1.0]` for valid inputs, this is equivalent to: `aggregate = floor(raw * 100 + 0.5) / 100` when evaluated in the same exact-decimal or fixed-point arithmetic model.
3. Set `confidence.aggregate` to this numeric value (quantized to two decimal places). When serializing JSON, producers MUST use the canonical JSON number form defined in section 6.5 (for example `0.90` MUST be serialized as `0.9`; `1.00` as `1`).

Threshold comparisons:

- Unless explicitly specified otherwise in section 8, threshold comparisons MUST use the unrounded `raw` value, not the serialized `aggregate`.
- For any entry where `confidence` is present and non-null, the threshold source of truth is the `raw` value computed from `confidence.dimensions` using the section 4 weights. Producers and consumers MUST compute and compare using that `raw` in the numeric computation model above; `confidence.aggregate` is a rounded serialization for reporting and stable output only.

Normative example (from section 3):

- `raw = 0.25*0.92 + 0.25*0.88 + 0.15*0.95 + 0.15*0.90 + 0.10*1.00 + 0.10*0.91 = 0.9185`
- Serialized `aggregate = round(0.9185, 2) = 0.92`
- Threshold checks compare using `raw = 0.9185`.

## 5. Human Confirmation States

Human status values are shared with project artifacts:

- `draft`
- `reviewed`
- `approved`
- `locked`

Meaning:

| Status | Meaning |
| --- | --- |
| `draft` | Machine-generated or unreviewed. |
| `reviewed` | Human has reviewed but not final-approved. |
| `approved` | Human accepts the translation or context. |
| `locked` | Must not be modified unless explicitly overridden. |

### 5.1 Staleness predicate (MVP)

A human-confirmed confidence record for a localization key MUST be treated as **stale** when either of the following is true:

- The recorded `source_content_hash` differs from the current authoritative entry’s `content_hash` for the same `key`.
- If the record was produced relative to an anchor, the recorded `anchor_context_hash` differs from the current context anchor’s hash for the same `key`.

Notes:

- `content_hash` is the stable per-entry hash produced by parsing/normalization (owned by the parser + project artifact schemas).
- The context anchor hash is owned by the context anchor schema; this spec only requires that a stable per-key hash exists and is recorded for staleness checks.

### 5.2 Deterministic skip behavior (MVP)

For incremental skip decisions:

- If `human_status` (resolved per section 5.3) is `approved` or `locked` **and** the record is not stale, implementations MUST treat the effective aggregate confidence as `1.0` for skip eligibility.
- If the record is stale, implementations MUST NOT treat it as `1.0` and MUST emit a finding indicating `stale_human_confirmation` for that `key`.
- `locked` additionally means no automatic write-back may modify the translation without an explicit override (write-back policy is owned by the translation workflow, but this status is authoritative).

### 5.3 Authoritative `human_status` source and precedence (MVP)

For each confidence report entry `(key, locale)`, the producer (Project Service) MUST resolve a single authoritative `human_status` value using project artifacts. This resolved value is the source of truth for section 5.2 and section 8 skip eligibility.

Authoritative source definition (MVP):

- `entry.human_status` MUST represent the human confirmation state of the **target translation** for the entry’s `(key, locale)`.

Resolution algorithm (MVP):

1. If project artifacts expose a **per-key** human status for the target localization entry `(key, locale)`, use that value.
2. Else, if project artifacts expose a **file-level** human status for the target localization file that contains `(key, locale)` (for example via localization inventory), use that value.
3. Else, set `human_status = "draft"`.

Conflict handling (MVP):

- If multiple candidate statuses exist at the same precedence level (for example duplicate/overlapping per-key records), producers MUST choose the most restrictive status using this total order:
  `locked` > `approved` > `reviewed` > `draft`.

## 6. Confidence Report Artifact (MVP contract)

A confidence report is a deterministic, run-scoped artifact written under the project report root.

### 6.1 Producer and consumers

- Producer: Project Service (project-first workflow orchestrator).
- Consumers: CLI operator, CI, humans reviewing confidence/context, downstream steps that decide whether provider-backed work was performed.

### 6.2 Persistence location and run scoping

- Report root for MVP is anchored at `<project-root>/reports/`.
- Confidence reports MUST be written under `<project-root>/reports/confidence/<run_id>/`.
- For MVP, each run directory MUST contain exactly one confidence report document at `<project-root>/reports/confidence/<run_id>/confidence.json`.
- The run directory MAY contain auxiliary, non-normative files, but consumers MUST NOT require them to parse or evaluate the confidence report.
- Reports MUST be run-scoped (do not silently overwrite prior runs).

Run identity (`run_id`) rules (MVP):

- `run_id` MUST be assigned and locked before any report writes. The CLI layer is the default owner of `run_id`; if the Project Service assigns it, it MUST do so before producing any report artifacts.
- The report envelope field `run_id` MUST exactly match the `<run_id>` path segment used in `<project-root>/reports/confidence/<run_id>/confidence.json`.
- `run_id` MUST be a non-empty string and MUST be safe to use as a single path segment (MUST NOT contain `/` or `\\`, and MUST NOT be `.` or `..`).
- If `<project-root>/reports/confidence/<run_id>/confidence.json` already exists, the run MUST fail and MUST NOT overwrite the prior report unless an explicit overwrite/new-run behavior is requested by the CLI (owned by the CLI command spec).

### 6.3 Report modes

`report_mode` MUST be one of:

- `standalone` (no anchor; may propose context descriptions)
- `relative_to_anchor` (anchor present and populated; evaluates relative to anchor)
- `provider_skipped` (provider-optional work was not performed; report still written)

### 6.4 Provider status

When provider-backed confidence generation is optional, the report MUST record `provider_status`:

- `used`
- `skipped_disabled`
- `skipped_unavailable`

Deterministic mapping (MVP):

- If provider-backed work is performed for this run, the report MUST set `provider_status: "used"`.
- If provider-backed work is not performed because provider access is disabled by configuration/operator policy, the report MUST set `provider_status: "skipped_disabled"`.
- If provider-backed work is not performed because provider access is enabled but the provider is unavailable (for example missing credentials or provider cannot be reached), the report MUST set `provider_status: "skipped_unavailable"`.

Relationship to `report_mode`:

- If `report_mode = "provider_skipped"`, `provider_status` MUST be one of `skipped_disabled` or `skipped_unavailable`.
- If `report_mode` is `standalone` or `relative_to_anchor`, `provider_status` MUST be `used`.

If provider-backed confidence generation is required and fails, the command exits with exit code `4` (provider failure), and the report-writing behavior is owned by the CLI command spec; this confidence spec does not require partial report output in that case.

### 6.5 Minimal report envelope (required fields)

A confidence report document MUST include, at minimum, the fields below.

Envelope schema (MVP):

| Field | Type | Required? | Nullable? | Rules |
| --- | --- | --- | --- | --- |
| `schema_version` | string | required | not null | MUST equal `"1.0"`. |
| `report_family` | string | required | not null | MUST equal `"confidence"`. |
| `report_mode` | string | required | not null | One of `standalone`, `relative_to_anchor`, `provider_skipped` (section 6.3). |
| `project_id` | string | required | not null | MUST be a non-empty string (stable project identifier). |
| `run_id` | string | required | not null | MUST be a non-empty string; MUST be safe as a single path segment (section 6.2). |
| `produced_at` | string | required | not null | RFC3339 timestamp. |
| `inputs` | object | required | not null | MUST include all nested `inputs.*` fields below. |
| `inputs.authoritative_file` | string | required | not null | MUST be a non-empty path or stable file ID. |
| `inputs.target_file` | string | required | not null | MUST be a non-empty path or stable file ID. |
| `inputs.context_anchor_present` | boolean | required | not null | See semantics below. |
| `inputs.context_anchor_valid` | boolean | required | not null | See semantics below. |
| `inputs.context_anchor_populated` | boolean | required | not null | See semantics below. |
| `provider` | object | optional | nullable allowed | Optional provider metadata; producers MAY omit or set null. MVP consumers MUST ignore this object if unsupported/unrecognized.
| `provider_status` | string | required | not null | One of `used`, `skipped_disabled`, `skipped_unavailable` (section 6.4).
| `entries` | array | required | not null | Array of confidence report entries (section 9). MAY be empty.
| `findings` | array | required | not null | Array of findings; MAY be empty.
| `summary` | object | required | not null | MUST conform to section 6.6.

Envelope forward-compatibility:

- Producers MAY include additional envelope fields.
- MVP consumers MUST ignore unknown envelope fields when parsing/validating the report.

Context anchor booleans (MVP semantics):

- `context_anchor_present` MUST be `true` iff the run was able to locate and read a `context-anchor.yaml` artifact; otherwise it MUST be `false`.
- `context_anchor_valid` MUST be `true` iff `context_anchor_present = true` and the artifact passes schema validation; otherwise it MUST be `false`.
- `context_anchor_populated` MUST be `true` iff `context_anchor_valid = true` and the parsed artifact contains one or more per-key context records; otherwise it MUST be `false`.
  - A schema-valid empty placeholder `context-anchor.yaml` (for example created by `parley project init`) is considered unpopulated.

Determinism requirements:

Report document serialization (MVP):

- Producers MUST serialize the `confidence.json` report document as `canonical_json(report)` for the full report object (the envelope containing `entries`, `findings`, and `summary`).
- Consumers that need stable comparisons (for example golden-file tests) MUST compare the bytes of `canonical_json(report)`; consumers that only need semantics MAY compare parsed structured content.

Sort ordering rules:

- Unless a field’s schema explicitly defines a different ordering, ordering comparisons MUST treat strings as ordered lexicographically by Unicode code point (ascending).
- For ordering comparisons, null/omitted values MUST sort after any present non-null value.
- Producers MUST ensure a **total order** for deterministic serialization. If two objects compare equal under the primary tuple for `entries` or `findings`, producers MUST apply the tie-breaker rule below.

Tie-breaker rule (MVP):

- Define `canonical_json(x)` as a deterministic JSON string for object `x` produced by:
  - serializing the full object `x` (including any forward-compatible additional fields),
  - sorting all JSON object keys lexicographically (by Unicode code point) at every nesting level before serialization,
  - emitting no insignificant whitespace,
  - preserving array element order as-is,
  - serializing strings deterministically:
    - The serialized JSON text MUST be encoded as UTF-8 with no BOM.
    - Strings MUST be serialized without Unicode normalization; the sequence of Unicode code points in the in-memory string is the sequence that is serialized.
    - For each string, implementations MUST emit:
      - `\"` for U+0022 QUOTATION MARK,
      - `\\\\` for U+005C REVERSE SOLIDUS,
      - `\b`, `\f`, `\n`, `\r`, `\t` for U+0008, U+000C, U+000A, U+000D, U+0009 respectively,
      - `\u00XX` (lowercase hex digits) for any other control character U+0000 through U+001F.
    - Implementations MUST NOT escape solidus (`/`) as `\/`.
    - For all other non-control characters (including non-ASCII), implementations MUST emit the character directly (UTF-8) and MUST NOT use `\uXXXX` escape sequences or surrogate-pair escapes.
  - serializing JSON numbers in a canonical form for lexicographic comparison:
    - MUST NOT use exponent notation (no `e` or `E`).
    - MUST use base-10 digits only, with an optional leading `-` for negative values.
    - Zero MUST be serialized as `0` (not `-0`, `0.0`, or `0.00`).
    - Non-zero integers MUST NOT include a decimal point.
    - Non-integers MUST use a decimal point and MUST include at least one digit on both sides (e.g., `0.7`, not `.7`).
    - MUST NOT include insignificant leading or trailing zeroes (e.g., `0.70` -> `0.7`).
- If the primary tuple comparison compares equal, producers MUST order the two objects by lexicographic comparison of `canonical_json(x)` (ascending).

`entries` ordering:

- `entries` MUST be ordered by the tuple `(locale, key, source_locale, source_content_hash, target_content_hash)` (ascending).

`findings` ordering:

- `findings` MUST be ordered by the tuple `(severity_rank, category, locale, file, key, message)` (ascending).
- `severity_rank` MUST be computed from `severity` using this rank order (lowest to highest): `info` < `warning` < `error` < `blocking`.
- If a finding `severity` is missing or not one of the four values above, it MUST sort after the ranked severities and then be ordered by the literal `severity` string.

Findings schema (MVP required fields):

Each finding in `findings[]` MUST be an object with these fields:

| Field | Type | Required? | Nullable? | Rules |
| --- | --- | --- | --- | --- |
| `severity` | string | required | not null | One of `info`, `warning`, `error`, `blocking`. |
| `category` | string | required | not null | MUST be one of: `structural`, `parser_syntax`, `localization_syntax`, `placeholder_integrity`, `spelling`, `grammar`, `clarity`, `terminology`, `semantic`, `artifact_schema`, `io`, `provider`. |
| `locale` | string | optional | nullable allowed | Locale associated with the finding; omit or null if not applicable. |
| `file` | string | optional | nullable allowed | File path or stable file ID associated with the finding; omit or null if not applicable. |
| `key` | string | optional | nullable allowed | Localization key associated with the finding; omit or null if not applicable. |
| `message` | string | required | not null | Human-readable message used in deterministic ordering. |

Forward-compatibility:

- Producers MAY include additional fields in findings.
- MVP consumers MUST ignore unknown fields when parsing/validating findings.

Entry coverage and identity semantics (MVP):

- `entries` MUST contain exactly one entry for each parsed localization entry present in the run’s `target_file` **for which a corresponding authoritative record exists** (the managed valid target set for this run), regardless of `report_mode`.
- For each entry, `key` and `locale` identify the target record; `source_content_hash` MUST be derived from the authoritative record for the same `key` (in `source_locale`), and `target_content_hash` MUST be derived from the target record.
- If a `key` exists in the target file but has no corresponding authoritative record, the run MUST emit a finding with `category: "structural"` and `severity: "error"` for that key. The confidence report MUST still be produced and MUST NOT include an `entries[]` entry for the unmanaged key (because the entry cannot be linked to an authoritative `source_content_hash`). Exit code behavior is owned by the CLI/validation taxonomy; this spec requires that the run’s confidence report is still written.
- If a `key` exists in the authoritative file but is missing from the target file, the run MUST emit a finding with `category: "structural"` and `severity: "error"` indicating the missing target entry; because no target record exists, no entry is produced for that key.

### 6.6 Minimal correctness report (summary)

`summary` MUST include, at minimum:

- `entry_count`: total number of entries (`len(entries)`).
- `below_human_review_recommended`: count of entries whose computed threshold `raw` (section 4.2) is below `human_review_recommended` (section 8).
- `below_generation_blocked`: count of entries whose computed threshold `raw` (section 4.2) is below `generation_blocked` (section 8).
- `confidence_unavailable_count`: count of entries whose `confidence` is omitted or null.
- `thresholds`: the thresholds used (values from section 8).

Deterministic computation (MVP):

- `summary.entry_count` MUST equal `len(entries)`.
- `below_human_review_recommended` and `below_generation_blocked` MUST be computed over entries with non-null `confidence` only.
- `confidence_unavailable_count` MUST equal the number of entries with omitted or null `confidence`.
- If `report_mode = "provider_skipped"`, `confidence_unavailable_count` MUST equal `entry_count`, and both below-threshold counts MUST be `0`.

## 7. Confidence Mode Decision Rules (context anchor + provider-optional)

Before any provider calls, implementations MUST complete artifact schema validation and precondition checks for required project artifacts.

Provider outcome classification (MVP):

- If provider-backed work is performed, set `provider_status: "used"`.
- If provider access is disabled by configuration/operator policy, set `provider_status: "skipped_disabled"`.
- If provider access is enabled but the provider is unavailable, set `provider_status: "skipped_unavailable"`.

Deterministic `context-anchor.yaml` state predicate (MVP):

- “Missing” means `inputs.context_anchor_present = false`.
- “Present but schema-invalid” means `inputs.context_anchor_present = true` and `inputs.context_anchor_valid = false`.
- “Present, schema-valid, effectively empty/unpopulated” means `inputs.context_anchor_valid = true` and `inputs.context_anchor_populated = false`.
- “Present, schema-valid, populated” means `inputs.context_anchor_populated = true`.

Confidence mode selection rules:

| `context-anchor.yaml` state | `provider_status` | `report_mode` | Required behavior |
| --- | --- | --- | --- |
| Missing | `used` | `standalone` | Generate standalone confidence entries and write report. |
| Missing | `skipped_disabled` | `provider_skipped` | Write provider-skipped confidence report (no silent omission). |
| Missing | `skipped_unavailable` | `provider_skipped` | Write provider-skipped confidence report (no silent omission). |
| Present but schema-invalid | N/A | N/A | Fail fast as artifact schema error (exit code `2`); no provider calls; do not attempt confidence generation. |
| Present, schema-valid, effectively empty/unpopulated | `used` | `standalone` | Treat as “no anchor” for confidence; generate standalone and write report. |
| Present, schema-valid, effectively empty/unpopulated | `skipped_disabled` | `provider_skipped` | Treat as “no anchor” for confidence; write provider-skipped report. |
| Present, schema-valid, effectively empty/unpopulated | `skipped_unavailable` | `provider_skipped` | Treat as “no anchor” for confidence; write provider-skipped report. |
| Present, schema-valid, populated | `used` | `relative_to_anchor` | Generate relative-to-anchor confidence entries and write report. |
| Present, schema-valid, populated | `skipped_disabled` | `provider_skipped` | Write provider-skipped report (still records anchor presence/validity/population). |
| Present, schema-valid, populated | `skipped_unavailable` | `provider_skipped` | Write provider-skipped report (still records anchor presence/validity/population). |

Obvious failure categories (MVP):

- Parser/IO failure reading input localization files (exit code `3`).
- Artifact schema invalid for required project artifacts (exit code `2`).
- Provider required/unavailable or provider failure when provider work is required (exit code `4`).

## 8. Thresholds

Default thresholds:

| Threshold | Value | Used by |
| --- | --- | --- |
| `min_context_for_generation` | `0.70` | Project-mode translation generation. |
| `min_reuse_score` | `0.88` | Translation memory reuse. |
| `high_confidence_skip` | `0.90` | Incremental skip for unchanged target strings. |
| `human_review_recommended` | `< 0.80` | Reports and terminal summaries. |
| `generation_blocked` | `< 0.70` | Translation generation unless override supplied. |

Threshold source-of-truth rule:

- Except for `high_confidence_skip` (defined below), threshold comparisons in this section MUST use the unrounded `raw` confidence computed from dimensions (section 4.2).

`high_confidence_skip` skip eligibility rule (MVP):

- For skip eligibility, implementations MUST compute a `skip_score` for each entry:
  - If `human_status` is `approved` or `locked` and the record is not stale per section 5.1, then `skip_score = 1.0`.
  - Otherwise (including stale approved/locked), `skip_score = raw` where `raw` is computed from dimensions per section 4.2.
- An entry is eligible for incremental skip iff `skip_score >= high_confidence_skip`.

Notes:

- This `skip_score` override is for skip eligibility only; report threshold summaries (section 6.6) continue to use `raw`.

Translation generation MUST NOT generate from a context entry whose unrounded threshold source-of-truth `raw` confidence (section 4.2) is below `0.70` unless the user provides an explicit override.

If the relevant confidence input for generation is missing, null, invalid, or otherwise cannot produce a `raw` value (section 4.2), translation generation MUST treat the entry as below `min_context_for_generation` / `generation_blocked` and MUST NOT generate unless an explicit override is supplied.

Override scope and project-mode preconditions:

- The overrides described in this section apply only to **threshold gating** after the project-mode translation workflow’s required preconditions have already passed.
- In project mode, `context-anchor.yaml` existence/validation/population requirements are owned by the translation workflow and the architecture HLD; an override for threshold gating (including bypassing `generation_blocked` or missing/unavailable confidence input) MUST NOT permit translation generation when `context-anchor.yaml` is missing, schema-invalid, or unpopulated. Those cases remain fail-fast precondition failures before any provider calls.

If a human-confirmed record is stale (section 5.2), it MUST be treated as not eligible for skip regardless of `high_confidence_skip`.

## 9. Confidence Report Entry

Each confidence report entry MUST include enough identity and linkage to support determinism and staleness checks.

### 9.1 Entry schema (MVP required fields)

Each entry MUST be an object with the fields below; some fields are conditionally required by `report_mode`.

| Field | Type | Required? | Nullable? | Rules |
| --- | --- | --- | --- | --- |
| `key` | string | required | not null | Localization key identifier. |
| `locale` | string | required | not null | Target locale for the entry. |
| `source_locale` | string | required | not null | Authoritative/source locale used for staleness and linkage. |
| `source_content_hash` | string | required | not null | Required for staleness checks (section 5.1). |
| `target_content_hash` | string | required | not null | Hash of the current target entry content for the same `key` and `locale`. |
| `confidence` | object | conditionally required | nullable allowed | A confidence object per section 3. Required and non-null for `standalone` and `relative_to_anchor`. MUST be omitted or null for `provider_skipped`. |
| `report_mode` | string | required | not null | Must match the report envelope `report_mode` (section 6.3). |
| `human_status` | string | required | not null | One of `draft`, `reviewed`, `approved`, `locked` (section 5). MUST be resolved deterministically per section 5.3. |
| `context_description` | string | conditionally required | nullable allowed | Required and non-null for `standalone`; optional for `relative_to_anchor`; MUST be null or omitted for `provider_skipped`. |
| `anchor_context_hash` | string | conditionally required | nullable allowed | Required and non-null for `relative_to_anchor`; MUST be null or omitted for `standalone` and `provider_skipped`. |
| `rationale` | string | optional | nullable allowed | May be produced by provider-backed analysis or deterministic validators. |
| `notes` | string | optional | nullable allowed | Free-form implementation notes; MVP allows null. |

Mode-specific rules:

- `standalone`:
  - `context_description` is required and MUST be a non-empty string.
  - `anchor_context_hash` MUST be omitted or null.
  - `confidence` MUST be present and valid per section 3.
- `relative_to_anchor`:
  - `anchor_context_hash` is required and MUST be a non-empty string.
  - `context_description` is optional; if present it MAY summarize anchor context but MUST NOT be treated as authoritative anchor content.
  - `confidence` MUST be present and valid per section 3.
- `provider_skipped`:
  - The entry MUST still include identity/linkage fields (`key`, `locale`, `source_locale`, `source_content_hash`, `target_content_hash`) and `human_status`.
  - `confidence` MUST be omitted or null.
  - `context_description`, `anchor_context_hash`, `rationale`, and `notes` MUST be omitted or null.

### 9.2 Example

```json
{
  "key": "ok_button",
  "locale": "fr-FR",
  "source_locale": "en-US",
  "source_content_hash": "sha256...",
  "target_content_hash": "sha256...",
  "confidence": {
    "dimensions": {
      "semantic": 0.92,
      "contextual": 0.88,
      "grammatical": 0.95,
      "terminology_compliance": 0.9,
      "placeholder_integrity": 1.0,
      "clarity": 0.91
    },
    "aggregate": 0.92,
    "method": "provider_assessed",
    "origin": "machine",
    "assessed_at": "2026-05-08T00:00:00Z"
  },
  "report_mode": "relative_to_anchor",
  "context_description": "Button allowing the user to affirm their choice.",
  "anchor_context_hash": "sha256...",
  "rationale": "The string is short but context clarifies button usage.",
  "notes": null,
  "human_status": "draft"
}
```

## 10. Minimal Confidence Report Example (envelope)

```json
{
  "schema_version": "1.0",
  "report_family": "confidence",
  "report_mode": "relative_to_anchor",
  "project_id": "proj_...",
  "run_id": "run_...",
  "produced_at": "2026-05-11T00:00:00Z",
  "inputs": {
    "authoritative_file": "localizations/authoritative/en.strings",
    "target_file": "localizations/targets/fr.strings",
    "context_anchor_present": true,
    "context_anchor_valid": true,
    "context_anchor_populated": true
  },
  "provider_status": "used",
  "entries": [],
  "findings": [],
  "summary": {
    "entry_count": 0,
    "below_human_review_recommended": 0,
    "below_generation_blocked": 0,
    "confidence_unavailable_count": 0,
    "thresholds": {
      "min_context_for_generation": 0.7,
      "min_reuse_score": 0.88,
      "high_confidence_skip": 0.9,
      "human_review_recommended": 0.8,
      "generation_blocked": 0.7
    }
  }
}
```