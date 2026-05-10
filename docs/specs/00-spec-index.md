# Parley Specification Index

## 1. Spec Set

This directory contains the v1 supporting specification set for Parley:

1. [CLI Command Specification](01-cli-command-spec.md)
2. [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
3. [Parser Interface and Format Specification](03-parser-interface-format-spec.md)
4. [Placeholder and Token Integrity Specification](04-placeholder-token-integrity-spec.md)
5. [Confidence Model Specification](05-confidence-model-spec.md)
6. [Translation Workflow Specification](06-translation-workflow-spec.md)
7. [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)
8. [Translation Memory Specification](08-translation-memory-spec.md)

## 2. Shared v1 Contracts

### 2.1 Schema Version

All v1 project artifacts, reports, parser payloads, and translation memory export records use:

```text
schema_version: "1.0"
```

### 2.2 CLI Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | Command succeeded with no blocking findings. |
| `1` | Command completed with blocking findings. |
| `2` | Usage, configuration, or artifact schema error. |
| `3` | Parser or file IO failure. |
| `4` | Required provider operation failed. |

### 2.3 Severities

- `info`
- `warning`
- `error`
- `blocking`

### 2.4 Validation Categories

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

### 2.5 Confidence Dimensions

- `semantic`
- `contextual`
- `grammatical`
- `terminology_compliance`
- `placeholder_integrity`
- `clarity`

### 2.6 Localization Formats

- `ios_strings`
- `android_xml`

### 2.7 Human Status and Approval Status

- `draft`
- `reviewed`
- `approved`
- `locked`

### 2.8 Translation Memory Provenance

- `machine_generated`
- `human_reviewed`
- `human_approved`
- `imported`

## 3. Interoperability Notes

- Parser diagnostics become validation findings using the shared category and severity enums.
- Placeholder validation always uses category `placeholder_integrity`.
- Glossary validation always uses category `terminology`.
- Confidence records use the same six dimensions in context anchors, reports, translation reports, and translation memory records.
- Translation workflow lookup order and translation memory lookup order are intentionally identical.
- Project-mode translation requires context anchor data; paired-file translation and paired semantic comparison do not use the project context anchor.
- Policy promotion can make a finding blocking for CI without mutating the original severity.

