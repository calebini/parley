# Confidence Model Specification

## 1. Scope

This specification defines confidence dimensions, score ranges, aggregation rules, human confirmation states, confidence report entries, and thresholds used by translation generation.

It depends on:

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Translation Workflow Specification](06-translation-workflow-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

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

If any required dimension is missing, the confidence object is invalid and artifact validation MUST fail with exit code `2`.

If validation emits a `blocking` finding for `placeholder_integrity`, the `placeholder_integrity` confidence MUST be `0.0`.

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

Human `approved` and `locked` records SHOULD be treated as aggregate confidence `1.0` for incremental skip decisions unless stale due to authoritative source changes.

## 6. Confidence Report Modes

### 6.1 Standalone

Used when no context anchor exists.

Each entry MUST include:

- `key`
- `confidence`
- `context_description`
- `notes` optional

Standalone reports may be promoted into `context-anchor.yaml` after human review.

### 6.2 Relative to Anchor

Used when context anchor exists.

Each entry MUST include:

- `key`
- `confidence`
- `anchor_context_hash`
- `rationale` optional
- `notes` optional

No context rewrite is required in this mode.

## 7. Thresholds

Default thresholds:

| Threshold | Value | Used by |
| --- | --- | --- |
| `min_context_for_generation` | `0.70` | Project-mode translation generation. |
| `min_reuse_score` | `0.88` | Translation memory reuse. |
| `high_confidence_skip` | `0.90` | Incremental skip for unchanged target strings. |
| `human_review_recommended` | `< 0.80` | Reports and terminal summaries. |
| `generation_blocked` | `< 0.70` | Translation generation unless override supplied. |

Translation generation MUST NOT generate from a context entry whose aggregate confidence is below `0.70` unless the user provides an explicit override.

## 8. Confidence Report Entry

```json
{
  "key": "ok_button",
  "locale": "fr-FR",
  "source_locale": "en-US",
  "confidence": {},
  "context_description": "Button allowing the user to affirm their choice.",
  "anchor_context_hash": "sha256...",
  "rationale": "The string is short but context clarifies button usage.",
  "notes": null,
  "human_status": "draft"
}
```

