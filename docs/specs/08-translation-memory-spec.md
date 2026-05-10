# Translation Memory Specification

## 1. Scope

This specification defines translation memory storage, lookup strategy, match scoring, provenance model, approval states, migration behavior, and JSONL import/export format.

It depends on:

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Confidence Model Specification](05-confidence-model-spec.md)
- [Translation Workflow Specification](06-translation-workflow-spec.md)

## 2. Storage Backend

The v1 local storage backend is SQLite.

Default file:

```text
<project-root>/translation-memory.sqlite
```

SQLite MUST be treated as machine-managed. Human review should happen through CLI commands, export files, or future UI tooling.

## 3. SQLite Schema

### 3.1 `schema_migrations`

| Column | Type | Constraints |
| --- | --- | --- |
| `version` | integer | primary key |
| `name` | text | not null |
| `applied_at` | text | RFC 3339 timestamp |

### 3.2 `memory_entries`

| Column | Type | Constraints |
| --- | --- | --- |
| `memory_id` | text | primary key |
| `project_id` | text | not null |
| `key` | text | not null |
| `source_locale` | text | not null |
| `target_locale` | text | not null |
| `source_text` | text | not null |
| `target_text` | text | not null |
| `source_content_hash` | text | not null |
| `target_content_hash` | text | not null |
| `placeholder_signature` | text | not null |
| `context_anchor_hash` | text | nullable |
| `glossary_version` | text | nullable |
| `provenance` | text | not null |
| `approval_status` | text | not null |
| `confidence_json` | text | not null |
| `metadata_json` | text | not null default `{}` |
| `created_at` | text | not null |
| `updated_at` | text | not null |

Required indexes:

```sql
CREATE INDEX idx_tm_exact
ON memory_entries (project_id, source_locale, target_locale, source_content_hash, placeholder_signature);

CREATE INDEX idx_tm_key_locale
ON memory_entries (project_id, key, source_locale, target_locale);

CREATE INDEX idx_tm_status
ON memory_entries (project_id, approval_status, provenance);
```

## 4. Provenance

Allowed `provenance` values:

- `machine_generated`
- `human_reviewed`
- `human_approved`
- `imported`

## 5. Approval Status

Allowed `approval_status` values:

- `draft`
- `reviewed`
- `approved`
- `locked`

`approval_status` uses the same semantic meaning as human status in project artifacts.

## 6. Lookup Strategy

Lookup order MUST match the translation workflow spec:

1. Exact approved or locked match by `source_content_hash`, target locale, and placeholder signature.
2. Exact reviewed match by `source_content_hash`, target locale, and placeholder signature.
3. Exact machine-generated match by `source_content_hash`, target locale, and placeholder signature.
4. Same key and target locale with compatible placeholder signature.
5. Fuzzy source text match with compatible context and placeholder signature.

Candidates with incompatible placeholder signatures MUST NOT be reused.

## 7. Match Scoring

Scores are `0.0..1.0`.

Base scoring:

| Match Type | Base Score |
| --- | --- |
| Exact source hash, approved or locked | `1.00` |
| Exact source hash, reviewed | `0.96` |
| Exact source hash, machine generated | `0.90` |
| Same key, compatible placeholder signature | `0.82` |
| Fuzzy source text and compatible context | `0.70..0.89` |

Adjustments:

- `+0.05` if context anchor hash matches, capped at `1.0`.
- `+0.03` if glossary version matches, capped at `1.0`.
- `-0.10` if context anchor hash differs.
- `-0.10` if glossary version differs and affected terms are present.
- `-0.20` if source text similarity is below `0.85`.

Default reuse threshold is `0.88`.

## 8. Conflict Handling

When importing or writing a record with the same exact key fields but different target text, conflict handling MUST follow the selected merge mode:

| Mode | Behavior |
| --- | --- |
| `prefer-approved` | Keep approved/locked over reviewed/draft; otherwise keep newer. |
| `prefer-newer` | Keep record with later `updated_at`. |
| `reject-conflicts` | Do not import conflicting record; emit import finding. |

Exact key fields:

- `project_id`
- `key`
- `source_locale`
- `target_locale`
- `source_content_hash`
- `placeholder_signature`

## 9. JSONL Import/Export Record

Each JSONL line MUST be:

```json
{
  "schema_version": "1.0",
  "memory_id": "tm-123",
  "project_id": "myapp",
  "key": "ok_button",
  "source_locale": "en-US",
  "target_locale": "fr-FR",
  "source_text": "OK",
  "target_text": "OK",
  "source_content_hash": "sha256...",
  "target_content_hash": "sha256...",
  "placeholder_signature": "",
  "context_anchor_hash": "sha256...",
  "glossary_version": "v1",
  "provenance": "human_approved",
  "approval_status": "approved",
  "confidence": {
    "dimensions": {
      "semantic": 1.0,
      "contextual": 1.0,
      "grammatical": 1.0,
      "terminology_compliance": 1.0,
      "placeholder_integrity": 1.0,
      "clarity": 1.0
    },
    "aggregate": 1.0,
    "method": "human_confirmed",
    "origin": "human",
    "assessed_at": "2026-05-08T00:00:00Z"
  },
  "metadata": {},
  "created_at": "2026-05-08T00:00:00Z",
  "updated_at": "2026-05-08T00:00:00Z"
}
```

## 10. Migration Rules

- Migrations MUST be ordered integer versions.
- Migrations MUST be idempotent when possible.
- Failed migrations MUST leave the previous schema usable or fail before mutating data.
- Export SHOULD be supported before destructive migrations.
