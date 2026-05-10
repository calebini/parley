# CLI Command Specification

## 1. Scope

This specification defines Parley's command surface, common options, command-specific arguments, exit codes, examples, and expected artifacts.

It depends on:

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Parser Interface and Format Specification](03-parser-interface-format-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

## 2. Global Command Shape

```text
parley [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS]
```

Global options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--project-root PATH` | path | nearest ancestor containing `parley.yaml` | Project root for project-mode commands. |
| `--output-format text|json` | enum | `text` | Terminal output format. Does not change report artifact format. |
| `--report-dir PATH` | path | `<project-root>/reports/<kind>/` | Directory for generated reports. |
| `--quiet` | boolean | `false` | Suppress non-error terminal output. |
| `--verbose` | boolean | `false` | Include diagnostic details. |
| `--no-provider` | boolean | `false` | Disallow external provider calls. |
| `--provider NAME` | string | project default | Provider adapter for semantic, confidence, or translation work. |

Path options are resolved relative to the current working directory unless otherwise stated.

## 3. Exit Codes

All commands MUST use the shared exit code table.

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | success | Command succeeded with no blocking findings. |
| `1` | blocking_findings | Command completed and produced at least one `blocking` validation finding. |
| `2` | usage_or_configuration_error | Invalid command usage, invalid option combination, missing project config, invalid artifact schema, or unsupported workflow. |
| `3` | parser_or_io_failure | Required file cannot be read/written, parser cannot parse an input file, or write-back fails. |
| `4` | provider_failure | Required external provider call failed or returned invalid output after retries. |

Validation findings with severity `info`, `warning`, or `error` do not by themselves force exit code `1`. CI policy may promote categories or severities to `blocking`; see [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md).

## 4. Shared Report Behavior

Commands that produce reports MUST write versioned JSON reports using the common report envelope from the artifact schema spec.

Report file naming:

```text
<report-dir>/<kind>/<yyyyMMdd-HHmmss>-<command-name>-<run-id>.json
```

`run_id` MUST be a stable unique ID for the command invocation. UUIDv7 is preferred.

Commands MUST print generated report paths unless `--quiet` is set.

## 5. Project Commands

### 5.1 `parley project init`

Initializes a Parley project.

```text
parley project init --name NAME --authoritative PATH --locale LOCALE [OPTIONS]
```

Options:

| Option | Type | Required | Description |
| --- | --- | --- | --- |
| `--name NAME` | string | yes | Human-readable project name. |
| `--authoritative PATH` | path | yes | Authoritative localization file. |
| `--locale LOCALE` | BCP 47 string | yes | Authoritative source language. |
| `--format FORMAT` | `ios_strings|android_xml` | no | Parser format override. |
| `--description TEXT` | string | no | Project-level description. |
| `--force` | boolean | no | Allow initialization in a directory containing existing Parley artifacts. |

Expected artifacts:

- `parley.yaml`
- `inventory.yaml`
- `canonical-inventory.json`
- Empty `context-anchor.yaml`
- Empty `glossary.yaml`
- `translation-memory.sqlite`
- Initialization report under `reports/validation/`

Example:

```text
parley project init --name MyApp --authoritative en.lproj/Localizable.strings --locale en-US
```

### 5.2 `parley project inspect`

Prints project metadata and artifact health.

```text
parley project inspect [--json]
```

Expected artifacts:

- No new artifacts unless `--report-dir` is supplied with `--json-report`.

## 6. Localization Commands

### 6.1 `parley localization add`

Adds an existing localization file to a project inventory and runs validation.

```text
parley localization add PATH --locale LOCALE [OPTIONS]
```

Options:

| Option | Type | Required | Description |
| --- | --- | --- | --- |
| `PATH` | path | yes | File to add. |
| `--locale LOCALE` | BCP 47 string | yes | Locale of the file. |
| `--format FORMAT` | `ios_strings|android_xml` | no | Parser format override. |
| `--role target|authoritative` | enum | no | Defaults to `target`; only one authoritative file may exist. |
| `--id ID` | string | no | Stable localization ID override. |
| `--status draft|reviewed|approved|locked` | enum | no | Defaults to `draft`. |
| `--confidence-mode anchor|standalone|none` | enum | no | Defaults to `anchor` if a context anchor exists, otherwise `standalone`. |

Expected artifacts:

- Updated `inventory.yaml`
- Validation report
- Confidence report unless `--confidence-mode none`

Example:

```text
parley localization add fr.lproj/Localizable.strings --locale fr-FR
```

### 6.2 `parley localization validate`

Validates one file, all project files, or a selected locale.

```text
parley localization validate [PATH] [--locale LOCALE] [OPTIONS]
```

Options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--scope structural|quality|all` | enum | `all` | Validation scope. |
| `--policy PATH` | path | project default | CI policy override. |
| `--write-report / --no-write-report` | boolean | `true` | Whether to persist a report. |

Expected artifacts:

- Validation report unless disabled.

Example:

```text
parley localization validate --locale fr-FR --scope all
```

### 6.3 `parley localization compare`

Compares localization files structurally and optionally semantically.

```text
parley localization compare [PATH ...] [OPTIONS]
```

Options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--mode structural|semantic|all` | enum | `structural` | Comparison mode. |
| `--against-authoritative` | boolean | `true` in project mode | Compare selected files to authoritative localization. |
| `--source PATH` | path | none | Source file for paired comparison. |
| `--target PATH` | path | none | Target file for paired comparison. |

In paired semantic comparison mode, the context anchor MUST NOT be used.

Expected artifacts:

- Comparison report under `reports/comparison/`

## 7. Context Commands

### 7.1 `parley context generate`

Generates or updates a context anchor proposal.

```text
parley context generate [OPTIONS]
```

Options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--mode standalone|update` | enum | `standalone` | Generate from authoritative strings or update existing anchor. |
| `--write-anchor` | boolean | `false` | Write accepted generated context into `context-anchor.yaml`. |
| `--min-confidence FLOAT` | number | `0.70` | Minimum aggregate confidence to auto-write when `--write-anchor` is set. |

Expected artifacts:

- Confidence report.
- Updated `context-anchor.yaml` only when `--write-anchor` is set.

### 7.2 `parley context report`

Reports contextual confidence.

```text
parley context report [--mode anchor|standalone]
```

Default mode is `anchor` when `context-anchor.yaml` contains per-key context, otherwise `standalone`.

Expected artifacts:

- Confidence report under `reports/confidence/`

## 8. Translation Commands

### 8.1 `parley translate`

Generates or updates a project target localization.

```text
parley translate --target-locale LOCALE [OPTIONS]
```

Options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--target-locale LOCALE` | BCP 47 string | required | Target locale to generate or update. |
| `--target-path PATH` | path | inventory path | Target file path if creating a new localization. |
| `--target-format FORMAT` | enum | authoritative format | Target parser/write format. |
| `--mode incremental|full` | enum | `incremental` | Translation scope. |
| `--include-approved` | boolean | `false` | Allow regeneration of human-approved translations. |
| `--include-locked` | boolean | `false` | Allow regeneration of locked translations. |
| `--dry-run` | boolean | `false` | Generate reports without writing target file or memory. |
| `--min-generate-confidence FLOAT` | number | `0.70` | Minimum source context confidence required for generation. |
| `--min-reuse-score FLOAT` | number | `0.88` | Minimum translation memory score for reuse. |

Project-mode translation requires a context anchor. Missing context anchor is exit code `2`.

Expected artifacts:

- Updated or created target localization file unless `--dry-run`.
- Translation report under `reports/translation/`.
- Validation report under `reports/validation/`.
- Updated translation memory unless `--dry-run`.

### 8.2 `parley translate file`

Secondary paired-file translation mode.

```text
parley translate file --source PATH --target PATH --source-locale LOCALE --target-locale LOCALE [OPTIONS]
```

This mode does not require a project and does not use the project context anchor. If `--project-root` is supplied, glossary and translation memory MAY be used, but the context anchor still MUST NOT be used for paired semantic comparison.

Expected artifacts:

- Updated or created target file unless `--dry-run`.
- Translation report in supplied report directory or current working directory.

## 9. Glossary Commands

### 9.1 `parley glossary validate`

Validates project localizations against glossary rules.

```text
parley glossary validate [--locale LOCALE]
```

Expected artifacts:

- Validation report containing `terminology` category findings.

## 10. Translation Memory Commands

### 10.1 `parley memory inspect`

Displays translation memory statistics.

```text
parley memory inspect [--locale LOCALE] [--key KEY]
```

### 10.2 `parley memory export`

Exports memory records.

```text
parley memory export --output PATH [--locale LOCALE] [--format jsonl]
```

Only `jsonl` is required for v1.

### 10.3 `parley memory import`

Imports memory records.

```text
parley memory import PATH [--merge prefer-approved|prefer-newer|reject-conflicts]
```

Expected artifacts:

- Updated `translation-memory.sqlite`.
- Import report under `reports/translation-memory/`.
