# CLI Command Specification

## 1. Scope

This specification defines Parley's command surface, common options, command-specific arguments, exit codes, examples, and expected artifacts.

It depends on:

- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Parser Interface and Format Specification](03-parser-interface-format-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)

Authority and navigation context:

- The Parley High-Level Design (HLD) is the architecture authority for project-first MVP boundaries, including project-scoped reports and the deferral of non-project paired-file translation.
- The Parley specification index is dependency/navigation context only; it does not override the HLD or this CLI leaf specification.

## 2. Global Command Shape

```text
parley [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGS]
```

Global options:

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `--project-root PATH` | path | nearest ancestor containing `parley.yaml` | Project root for project-mode commands. |
| `--output-format text|json` | enum | `text` | Terminal output format. Does not change report artifact format. |
| `--report-dir PATH` | path | `<project-root>/reports/` | Report root directory for generated reports. In the MVP, the resolved path MUST remain under `<project-root>/reports/`. |
| `--quiet` | boolean | `false` | Suppress non-error terminal output. |
| `--verbose` | boolean | `false` | Include diagnostic details. |
| `--no-provider` | boolean | `false` | Disallow external provider calls. |
| `--provider NAME` | string | project default | Provider adapter for semantic, confidence, or translation work. |

Terminal output contracts (MVP):

- `--output-format` controls stdout formatting for commands that emit terminal output.
- `--quiet` suppresses non-error stdout. Errors and failure details MUST be written to stderr regardless of `--output-format`.
- `--verbose` MAY add additional detail, but MUST NOT change required fields or the minimum JSON/text shapes below.

Report-writing command terminal output contract (MVP):

- This contract applies to commands that may persist one or more report artifacts (for example `parley project init`, `parley localization add`, `parley validate`, and `parley translate`).
- For these commands, unless `--quiet` is set, the command MUST write a terminal summary to stdout even when the invocation writes zero report artifacts (for example due to a pre-eligibility exit).

`--output-format text` minimum output (MVP):

- Print at minimum:
  - `command=<canonical_command>`
  - `exit_code=<exit_code>`
  - `reports_written=<n>`
- If one or more report artifacts were persisted, also print one line per report artifact path in the stable persisted-path order: `report=<path>`.

`--output-format json` output shape (MVP):

- Print exactly one JSON object with required fields:

```json
{
  "command": "<canonical_command>",
  "exit_code": 0,
  "reports": [
    {"kind": "validation|confidence|translation|other", "path": "<absolute-or-project-root-relative-path>"}
  ]
}
```

- `reports` MUST be an array (possibly empty) in stable persisted-path order.

Path options are resolved relative to the current working directory unless otherwise stated.

Project-root resolution:

- For project-mode commands (all commands except `parley project init`), `--project-root` defaults to the nearest ancestor directory containing `parley.yaml`. If no `parley.yaml` exists in any ancestor and `--project-root` is not provided, the command MUST fail with exit code `2`.
- For `parley project init`, `--project-root` MAY be provided even when no `parley.yaml` exists. If `--project-root` is not provided, the project root is the current working directory.

Report-root resolution (MVP):

- `--report-dir` defaults to `<project-root>/reports/`.
- If `--report-dir` is a relative path, it MUST be resolved relative to `<project-root>/reports/`, not the current working directory.
- The resolved `--report-dir` MUST remain under `<project-root>/reports/` under the project-root-relative path canonicalization and containment rule defined in 6.1. Otherwise the command MUST fail with exit code `2`.

Provider enablement (MVP):

- Commands MUST treat provider-backed work as explicitly required or optional per command.
- If a command requires provider-backed work and `--no-provider` is set, the command MUST fail fast with exit code `2` and MUST NOT perform any provider calls.
- If a command requires provider-backed work and provider calls are allowed but the provider is unavailable or fails, the command MUST fail with exit code `4`.
- If a command's provider-backed work is optional, `--no-provider` or provider unavailability MUST NOT be treated as an error; the command MUST still write the relevant report and MUST explicitly record `provider_status` as `skipped` rather than silently omitting output.
- If a command's provider-backed work is optional and provider-backed work is attempted but the provider fails (including returning invalid required output), the command MUST still write the relevant report and MUST explicitly record `provider_status` as `failed`. This MUST NOT be treated as an exit code `4` solely due to the provider failure. The command MUST preserve its command-specific managed-artifact mutation rules; the exit code is determined by non-provider outcomes (with required-report write failure still forcing exit code `3` per precedence).

Provider status reporting (MVP):

- Any report written by a command whose contract includes provider-backed work (whether required or optional) MUST include a required field `provider_status` with a closed enum value:
  - `not_applicable`: this command invocation cannot perform provider-backed work by contract.
  - `used`: one or more provider calls were attempted for this invocation.
  - `skipped`: provider-backed work could have been attempted but was not (for example `--no-provider`, provider unavailable in an optional context, or provider not needed after deterministic short-circuiting).
  - `failed`: provider-backed work was required or attempted and the provider failed or returned invalid required output.
- If `provider_status` is `skipped`, the report MUST include a required field `provider_skip_reason` with a closed enum value:
  - `no_provider`: provider calls were disallowed by `--no-provider`.
  - `unavailable`: the provider was unavailable and provider work was optional.
  - `not_needed`: the command deterministically determined no provider calls were needed (for example no provider-eligible work).
- If `provider_status` is `failed`, the report MUST include a required field `provider_failure_category` with a closed enum value:
  - `unavailable`: the provider was unavailable.
  - `invalid_output`: the provider returned output that failed required output validation.
  - `error`: any other provider failure (including API errors or timeouts).

Parser format resolution (MVP):

- This rule applies to any command that parses or writes a localization file and exposes an explicit format option (for example `--format` or `--target-format`).
- If an explicit format option is provided, the CLI MUST use that parser/write format.
  - If the provided format value is not supported, the command MUST fail with exit code `2`.
- If an explicit format option is omitted, the CLI MUST resolve the format deterministically using the first matching rule below:
  1. If the input file corresponds to exactly one `inventory.yaml` localization entry and that entry declares `format`, use the inventory `format`.
  2. Otherwise, infer from the file extension using the following mapping:
     - `.strings` -> `ios_strings`
     - `.xml` -> `android_xml`
  3. If no rule selects a format (unknown extension / missing inventory format), the command MUST fail with exit code `2`.
- If a format is selected but the parser cannot parse the file content (including format/content mismatch), the command MUST fail with exit code `3`.
- If a path-based inventory lookup yields multiple matching localization entries (for example duplicate inventory records for the same canonicalized project-relative path), the command MUST fail with exit code `2`.

## 3. Exit Codes

All commands MUST use the shared exit code table.

| Code | Name | Meaning |
| --- | --- | --- |
| `0` | success | Command succeeded with no blocking findings. |
| `1` | blocking_findings | Command completed and produced at least one `blocking` validation finding. |
| `2` | usage_or_configuration_error | Invalid command usage, invalid option combination, missing project config, invalid artifact schema, or unsupported workflow. |
| `3` | parser_or_io_failure | Required file cannot be read/written, parser cannot parse an input file, or write-back fails. |
| `4` | provider_required_failed | Required provider operation failed. |

Exit code precedence (MVP):

- If a command requires writing a report artifact and report writing fails, the command MUST exit with code `3`.
- Otherwise, if the command fails due to invalid usage, configuration, or artifact schema errors, the command MUST exit with code `2`.
- Otherwise, if provider-backed required work fails, the command MUST exit with code `4`.
- Otherwise, if the command has blocking findings, it MUST exit with code `1`.
- Otherwise, the command MUST exit with code `0`.

## 4. Report Naming and Persistence (MVP)

Report-root contracts:

- All report artifacts MUST be written under the resolved `--report-dir` which MUST remain under `<project-root>/reports/`.
- Reports MUST be placed under a command-specific subdirectory under the resolved `--report-dir` (for example `<resolved --report-dir>/validation/`, `<resolved --report-dir>/translation/`, `<resolved --report-dir>/comparison/`, `<resolved --report-dir>/confidence/`, `<resolved --report-dir>/translation-memory/`).
- Reports MUST be run-scoped by default: a new run MUST NOT silently overwrite prior run reports.

Run id and filename scheme (MVP):

- Each invocation that writes reports MUST set `started_at` to the invocation start time in UTC RFC 3339 format with microseconds: `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
- Each invocation that writes reports MUST derive `run_id` deterministically from `started_at` and a stable per-process nonce:
  - The per-process nonce MUST be 16 random bytes generated once per Parley process start and represented as lowercase hex (32 chars).
  - The `run_id` MUST be `<started_at_compact>-<process_nonce_hex>` where `<started_at_compact>` is `started_at` with punctuation removed: `YYYYMMDDTHHMMSSffffffZ`.
- The report filename MUST include the command name (canonicalized) and the run id, and MUST be:

```text
<canonical_command>--<run_id>.json
```

- If the derived report path already exists, the command MUST treat it as a report-write failure: it MUST NOT overwrite the existing file, and MUST exit with code `3`.

Canonical command names (MVP):

- `canonical_command` is a closed string mapping for the MVP command surface.
- Both the report filename prefix (`<canonical_command>`) and the report envelope `command` field MUST use exactly the values below.

| CLI command | `canonical_command` |
| --- | --- |
| `parley project init` | `project_init` |
| `parley project inspect` | `project_inspect` |
| `parley localization add` | `localization_add` |
| `parley validate` | `validate` |
| `parley translate` | `translate` |

Minimal report envelope (MVP):

- All reports MUST be schema-valid under the report envelope defined by the Project Artifact Schema Specification.
- Each report MUST include at minimum:
  - `schema_version: "1.0"`
  - `command`: canonical command name
  - `project_root`: resolved `<project-root>`
  - `run_id`: stable run id for this invocation
  - `started_at`: UTC RFC 3339 with microseconds: `YYYY-MM-DDTHH:MM:SS.ffffffZ`
  - `finished_at`: UTC RFC 3339 with microseconds: `YYYY-MM-DDTHH:MM:SS.ffffffZ`
  - `exit_code`: final exit code for this invocation
- `finished_at` MUST be captured deterministically after the command has determined its final `exit_code` and after preparing the final report contents in memory, and immediately before persisting the report artifact to its final path.

Deterministic ordering within reports (MVP):

- Any report field that is an array and is visible in persisted report artifacts MUST be written in a deterministic order.
- For validation reports (any report written under `<resolved --report-dir>/validation/`), the `findings` array MUST be sorted deterministically before persistence by the stable tuple below (ascending unless noted):
  - `locale` (lexical; empty string if missing)
  - `path` (lexical; empty string if missing)
  - `localization_id` (lexical; empty string if missing)
  - `key` (lexical; empty string if missing)
  - `category` (lexical; empty string if missing)
  - `severity` rank (higher severity first): `blocking` > `error` > `warning` > `info` (treat unknown as lowest).
  - `failure_category` (lexical; empty string if missing)
  - `code` (lexical; empty string if missing)
  - `stable_id` (lexical; empty string if missing)
  - `message` (lexical; empty string if missing)
- The finding shape and which of these fields are present is owned by `07-validation-error-taxonomy-spec.md`; this CLI spec only requires that the report writer compute a closed stable sort key from the available finding fields and apply it before writing the report file.

## 5. Project Commands

### 5.1 `parley project init`

Initializes a new Parley project in an empty directory.

```text
parley project init [--project-root PATH] --name NAME --authoritative PATH --locale LOCALE [--format FORMAT] [--force]
```

Options:

| Option | Type | Required | Description |
| --- | --- | --- | --- |
| `--project-root PATH` | path | no | Target directory to initialize; defaults to current working directory. |
| `--name NAME` | string | yes | Project name. |
| `--authoritative PATH` | path | yes | Authoritative localization file path (under project root). |
| `--locale LOCALE` | BCP 47 string | yes | Locale of authoritative file. |
| `--format FORMAT` | `ios_strings|android_xml` | no | Authoritative parser format override. |
| `--force` | boolean | no | Replace any existing Parley artifacts under project root. |

Project-root and emptiness rules (MVP):

- If `--project-root` is provided, the command MUST treat that directory as the target `<project-root>`.
- If `--project-root` is omitted, the command MUST treat the current working directory as `<project-root>`.
- If `--force` is not provided and any of the following paths exist under the target directory (exact path match), the command MUST fail with exit code `2` and MUST NOT modify existing artifacts: `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, `glossary.yaml`, `translation-memory.sqlite`, `.parley/`, `reports/`.
- If `--force` is provided:
  - The command MUST remove and recreate `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, and `glossary.yaml`.
  - If `translation-memory.sqlite` already exists and `--force` is provided, the command MUST replace it with a newly created empty database.
  - If `.parley/` already exists and `--force` is provided, the command MUST preserve its existing contents; it MAY create additional required subdirectories/files under `.parley/` but MUST NOT delete or rewrite unrelated `.parley/` contents.
  - If `<project-root>/reports/` already exists and `--force` is provided, the command MUST preserve existing reports and MUST NOT delete or overwrite prior report files under `<project-root>/reports/`; it MUST only add a new initialization report under `<resolved --report-dir>/validation/` following the shared report naming rules.
- With or without `--force`, the command MUST complete all input validation and all derivation work before deleting, replacing, or committing any managed artifact. This includes resolving `<project-root>`, canonicalizing and validating `--authoritative PATH`, determining parser format, reading/parsing the authoritative localization file, deriving the authoritative inventory record, deriving the canonical inventory, and preparing the schema-valid empty `context-anchor.yaml` placeholder, schema-valid empty `glossary.yaml` placeholder, the translation memory database, and the initialization report.
- For `--force`, delete/replace behavior is part of the final commit step only. If any validation, parse, derivation, staging, or report-preparation step fails before the commit point, the command MUST exit with the applicable code (`2` for invalid usage/config/schema; `3` for IO/parser failure) and MUST leave existing managed artifacts (including reports) unchanged.
- The final commit order for `--force` MUST be deterministic: first stage all replacement file contents and the initialization report outside their final paths, then atomically commit them as a single unit by replacing `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, `glossary.yaml`, `translation-memory.sqlite` and adding the initialization report under `<resolved --report-dir>/validation/`. The command MUST NOT delete `.parley/` or `<project-root>/reports/` as directories during this commit.
- If any atomic commit step fails after it begins (including failure to persist the initialization report), the command MUST exit with code `3` and MUST rollback the entire commit unit:
  - For any managed artifact path in the commit unit that existed before invocation, restore its exact pre-invocation contents.
  - For any managed artifact path in the commit unit that did not exist before invocation, remove it.
  - Remove the initialization report for this invocation if it was already placed at its final path.
  - It MUST NOT leave a mix of old and new core project artifacts that can be mistaken for a successful initialization.
- The command MUST NOT delete or modify non-Parley files under the target directory, including any existing localization files (such as the file at `--authoritative PATH`).
- The command MUST write a new initialization report under `<resolved --report-dir>/validation/`.

Initialization artifact contracts (MVP):

- The command MUST create an initial authoritative localization inventory record in `inventory.yaml` for the file identified by `--authoritative PATH`.
- The command MUST canonicalize `--authoritative PATH` to a project-root-relative path using the canonicalization rules defined in 6.1 (treating `PATH` as resolved from the current working directory).
  - If the resolved authoritative path is not under `<project-root>`, the command MUST fail with exit code `2`.
- The command MUST normalize the authoritative locale value by lowercasing ASCII letters. This normalized value is the inventory record `locale`.
- The command MUST set the authoritative inventory record `role` to `authoritative`.
- The command MUST set the authoritative inventory record `status` to `draft`.
- The command MUST determine and persist the authoritative inventory record `format` deterministically:
  - If `--format` is provided, the command MUST use that format.
  - Otherwise, the command MUST infer from the authoritative file extension using the global parser format resolution mapping.
  - If no rule selects a format (unknown extension), the command MUST fail with exit code `2`.
- The command MUST assign a stable `localization_id` for the authoritative inventory record using the stable localization ID derivation rule defined in 6.1, treating the normalized locale and canonicalized project-relative path as inputs:

```text
<normalized_locale>::<project_rel_path>
```

- The command MUST create `parley.yaml` such that it references the authoritative inventory record's `localization_id` as the project's authoritative localization.
- The command MUST create `canonical-inventory.json` deterministically from the authoritative localization file.
  - If the authoritative file cannot be read, or the parser cannot parse it (including format/content mismatch), or write-back fails for required artifacts, the command MUST fail with exit code `3`.

Atomicity (MVP):

- This command modifies multiple managed artifacts.
- In the MVP, these atomicity/rollback guarantees are defined only for normal command completion (the process returns an exit code). Crash/power-loss recovery is out of scope for the MVP; a crash may leave staged files or a partially-committed final state.
- If the command exits with code `3`, it MUST NOT leave a partially-initialized managed artifact set under `<project-root>`. In particular, it MUST NOT leave a directory containing only a strict subset of: `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, `glossary.yaml`, `translation-memory.sqlite`.
- If the command exits with code `3` due to any staging/commit failure (including initialization report persistence failure), it MUST leave the pre-invocation Parley core artifacts and reports under `<project-root>` unchanged:
  - Under `--force`, pre-existing managed artifacts in the commit unit MUST be restored to their exact pre-invocation contents.
  - For a first-time initialization where these managed artifacts did not exist pre-invocation, none of the managed artifacts in the commit unit (including the initialization report) may remain after the command returns.

Expected artifacts:

- `parley.yaml`
- `inventory.yaml`
- `canonical-inventory.json`
- Schema-valid empty `context-anchor.yaml` placeholder
- Schema-valid empty `glossary.yaml` placeholder
- `translation-memory.sqlite`
- Initialization report under `<resolved --report-dir>/validation/`

Context-anchor authority (MVP):

- `context-anchor.yaml` is created as a schema-valid empty placeholder by `parley project init`.
- In the MVP, population of per-key context is a manual (human-authored) workflow: users MAY edit `context-anchor.yaml` directly, and no CLI command in this spec is required to auto-populate per-key context.
- `parley localization add` and `parley translate` only consume and validate `context-anchor.yaml`; they MUST NOT mutate it.

Example:

```text
parley project init --name MyApp --authoritative en.lproj/Localizable.strings --locale en-US
```

### 5.2 `parley project inspect`

Prints project metadata and artifact health.

```text
parley project inspect
```

Inspection contract (MVP):

- The command MUST resolve `<project-root>` using the global project-root resolution rules.
  - If `--project-root` is explicitly provided, the command MUST treat that directory as `<project-root>` even if `parley.yaml` is missing, and MUST report the missing/invalid state rather than failing early solely because `parley.yaml` is absent.
- The command MUST check the health of the following project artifact paths under `<project-root>` (exact relative path match):
  - `parley.yaml`
  - `inventory.yaml`
  - `canonical-inventory.json`
  - `context-anchor.yaml`
  - `glossary.yaml`
  - `translation-memory.sqlite`
  - `reports/`
  - `.parley/`
- For each file artifact listed above, the command MUST classify its health deterministically into exactly one of the following statuses:
  - `present`: the file exists and is readable.
  - `missing`: the file does not exist.
  - `schema_invalid`: the file exists and is readable, but is not schema-valid under its owning artifact schema.
  - `io_error`: the file exists but cannot be read due to IO/permissions.
- For directory artifacts (`reports/`, `.parley/`), the command MUST classify status deterministically as `present`, `missing`, or `io_error`.
- When emitting an artifact list in terminal output (text or json), the command MUST use a stable ordering matching the artifact order listed above.

Terminal output format is controlled by the global `--output-format` option.

`--output-format text` minimum output (MVP):

- Unless `--quiet` is set, the command MUST print at minimum:
  - The resolved `<project-root>` path.
  - One line per checked artifact in the stable order, including its status.

`--output-format json` output shape (MVP):

- Unless `--quiet` is set, the command MUST print exactly one JSON object with the following required fields:

```json
{
  "project_root": "<resolved project root>",
  "artifacts": [
    {
      "artifact": "parley.yaml",
      "path": "<project-root>/parley.yaml",
      "kind": "file",
      "status": "present|missing|schema_invalid|io_error"
    }
  ]
}
```

Exit behavior (MVP):

- If any checked artifact has status `io_error`, the command MUST exit with code `3`.
- Otherwise, if any checked schema-bearing file artifact (`parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, `glossary.yaml`, `translation-memory.sqlite`) is `missing` or `schema_invalid`, the command MUST exit with code `2`.
- Otherwise, the command MUST exit with code `0`.

Expected artifacts:

- No new artifacts.

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
| `--confidence-mode anchor|standalone|none` | enum | no | Defaults to `anchor` only when `context-anchor.yaml` exists, is schema-valid, and contains populated per-key context; otherwise `standalone`. |

Project-root-relative path canonicalization and containment (MVP):

- This rule is used for:
  - Inventory record `path` values.
  - Path-based inventory lookup.
  - Stable `localization_id` derivation when `--id` is omitted.
  - `--report-dir` containment under `<project-root>/reports/` (section 2).
  - `parley translate --target-path` matching.
- The rule takes three inputs:
  - `<project-root>`: the resolved project root directory path.
  - `input_path`: the user-provided path value.
  - `resolution_base`: an absolute directory path.
- Resolution base selection:
  - For `parley localization add PATH`, `resolution_base` is the current working directory.
  - For `parley project init --authoritative PATH`, `resolution_base` is the current working directory.
  - For `parley translate --target-path PATH`, `resolution_base` is the current working directory.
  - For `--report-dir PATH` when PATH is relative, `resolution_base` is `<project-root>/reports/` (per section 2).
- Canonicalization algorithm:
  1. Resolve `resolved_abs_path`:
     - If `input_path` is absolute, set `resolved_abs_path = input_path`.
     - Otherwise, set `resolved_abs_path = resolution_base / input_path`.
  2. Normalize `resolved_abs_path` lexically:
     - Convert path separators to `/`.
     - Remove `.` segments.
     - Collapse `..` segments. If collapsing would traverse above the filesystem root, fail with exit code `2`.
     - Remove any trailing `/` (except `/` itself).
  3. Normalize `<project-root>` absolute path using the same separator and dot-segment rules.
  4. Containment check:
     - The normalized `resolved_abs_path` MUST be under normalized `<project-root>` by lexical prefix (`<project-root>` exactly, or `<project-root>/...`). Otherwise fail with exit code `2`.
     - Symlinks are not dereferenced for containment in the MVP; containment is lexical after normalization.
  5. Derive `project_rel_path`:
     - `project_rel_path` is the relative path from normalized `<project-root>` to normalized `resolved_abs_path`, using `/` separators.
     - `project_rel_path` MUST NOT start with `/`.
     - `project_rel_path` MUST NOT start with `./`.
     - `project_rel_path` MUST NOT end with `/`.
- Case sensitivity:
  - The canonicalized `project_rel_path` and containment prefix comparisons are lexical and MUST NOT apply case folding.

Stable localization ID derivation (MVP):

- The command MUST normalize the `--locale` value by lowercasing ASCII letters. This normalized value is the inventory record `locale`.
- If `--id ID` is provided, the command MUST use it as the `localization_id`.
- Otherwise:
  - The command MUST canonicalize `PATH` to `project_rel_path` using the canonicalization rule above.
  - The command MUST derive `localization_id` as:

```text
<normalized_locale>::<project_rel_path>
```

Confidence-mode default selection (MVP):

- If `--confidence-mode` is explicitly provided, the command MUST use that value.
- If `--confidence-mode anchor` is explicitly provided, the command MUST require `context-anchor.yaml` to exist, be schema-valid, and contain populated per-key context for this project.
  - If `context-anchor.yaml` is missing, the command MUST fail with exit code `2`, MUST NOT attempt provider calls, MUST NOT modify managed artifacts, MUST write only the validation report for this invocation, and MUST record the failure as a `blocking` finding against `context-anchor.yaml` with category `artifact_schema` and failure_category `missing`.
  - If `context-anchor.yaml` is schema-invalid, the command MUST fail with exit code `2`, MUST NOT attempt provider calls, MUST NOT modify managed artifacts, MUST write only the validation report for this invocation, and MUST record the failure as a `blocking` finding against `context-anchor.yaml` with category `artifact_schema` and failure_category `schema_invalid`.
  - If `context-anchor.yaml` is schema-valid but lacks populated per-key context, the command MUST fail with exit code `2`, MUST NOT attempt provider calls, MUST NOT modify managed artifacts, MUST write only the validation report for this invocation, and MUST record the failure as a `blocking` finding against `context-anchor.yaml` with category `artifact_schema` and failure_category `context_incomplete`.
  - In all three explicit-anchor failure cases, the command MUST NOT write a confidence report.
- If `--confidence-mode` is omitted, the command MUST select the default deterministically as follows:
  1. If `context-anchor.yaml` is missing, select `standalone`.
  2. The command MUST evaluate `context-anchor.yaml` schema validity only after the invocation is validation-report-eligible (see Validation report eligibility and Operation order).
     - If the invocation fails after reaching validation report eligibility due to `PATH` being unreadable or unparsable, the command MUST set the outcome exit code to `3`, MUST write exactly one validation report, and MUST NOT write a confidence report, regardless of `context-anchor.yaml` state.
  3. If `context-anchor.yaml` exists but is schema-invalid (evaluated only after eligibility is met), the command MUST fail with exit code `2`.
     - The command MUST NOT attempt any provider calls.
     - The command MUST NOT modify `inventory.yaml`, `parley.yaml`, `canonical-inventory.json`, or any other managed artifacts.
     - The command MUST write its validation report (with `provider_status=not_applicable`) and MUST NOT write a confidence report.
  4. Otherwise (`context-anchor.yaml` exists and is schema-valid), determine whether it contains populated per-key context for this project.
     - The canonical key set is the key order defined by `canonical-inventory.json`.
     - For MVP determinism, “populated per-key context” means: for every canonical key in this set, the context anchor provides a non-empty (after trimming whitespace) context value for that key.
     - Extra keys in the context anchor MUST NOT affect the predicate.
     - Whitespace-only context values MUST be treated as empty.
  5. If the predicate holds, select `anchor`; otherwise select `standalone`.

Provider behavior (confidence, MVP):

- Validation work for this command is local-only and MUST NOT require provider-backed work.
  - The validation report written for this command (under `<resolved --report-dir>/validation/`) MUST set `provider_status=not_applicable`.
- If `--confidence-mode none`:
  - Provider-backed work is `not_applicable` for this invocation.
  - The command MUST NOT write a confidence report.
- If `--confidence-mode anchor` or `standalone`:
  - Provider-backed confidence work is optional.
  - For validation-report-eligible invocations whose outcome exit code is `0` or `1`, the command MUST write a confidence report under `<resolved --report-dir>/confidence/` using the shared report naming and minimal envelope rules.
  - Otherwise (outcome exit code is `2` or `3`), the command MUST NOT write a confidence report.
  - The confidence report MUST include `provider_status` (and required conditional provider fields) per the global Provider status reporting contract.
  - If `--no-provider` is set:
    - The command MUST NOT attempt any provider calls.
    - The confidence report MUST set `provider_status=skipped` and `provider_skip_reason=no_provider`.
    - The command MUST continue and must not treat this as an error.
  - Otherwise, if the provider is unavailable or fails during confidence evaluation:
    - The confidence report MUST set `provider_status=failed` and `provider_failure_category=unavailable|error|invalid_output` as appropriate.
    - The command MUST continue and must not treat this as an error.

Validation report preconditions (MVP):

- This command MUST require a schema-valid `<project-root>` and Parley project artifacts.
- The command MUST read and schema-validate `inventory.yaml`.
- The command MUST require and schema-validate the following artifacts:
  - `canonical-inventory.json` for all invocations that validate a target localization entry (this command's core path), independent of confidence mode.
  - `parley.yaml` when `--role authoritative` is requested.
  - `context-anchor.yaml` when confidence mode is `anchor` (explicit or default).
- If any required artifact is missing, the command MUST set the outcome exit code to `2`, MUST NOT attempt any provider calls, MUST NOT stage any managed-artifact mutations, MUST later write only the validation report for this invocation, and MUST record the failure as a `blocking` finding against the missing artifact with category `artifact_schema` and failure_category `missing`.
- If any required artifact is schema-invalid, the command MUST set the outcome exit code to `2`, MUST NOT attempt any provider calls, MUST NOT stage any managed-artifact mutations, MUST later write only the validation report for this invocation, and MUST record the failure as a `blocking` finding against the invalid artifact with category `artifact_schema` and failure_category `schema_invalid`.
- If multiple required artifacts fail these preconditions, the command MUST include a `blocking` finding for each failed artifact in the validation report and MUST still write exactly one validation report for the invocation (subject to normal report eligibility and report-write failure precedence).

Validation scope (structural baseline, MVP):

- For validation-report-eligible invocations that reach file-parse success for `PATH`, the validation report MUST include structural findings derived from `canonical-inventory.json` as the baseline:
  - Missing keys (present in `canonical-inventory.json` but absent from the parsed `PATH`).
  - Extra keys (present in parsed `PATH` but absent from `canonical-inventory.json`).
  - Placeholder-signature mismatches between parsed `PATH` and the canonical placeholder signatures recorded in `canonical-inventory.json`.
- The detailed finding schema, codes, and category mapping are owned by `07-validation-error-taxonomy-spec.md`; this CLI spec only requires that these structural/placeholder baseline mismatches are surfaced as findings rather than silently skipped.

Validation report eligibility (MVP):

- Validation report persistence requirements apply only after the command has successfully:
  - Resolved `<project-root>` and the resolved report root (`--report-dir`).
  - Resolved the effective parser format for `PATH`.
- If the command fails with exit code `2` before reaching this eligibility point (for example: project-root/report-root resolution failures, or invalid parser-format selection), the command MUST NOT write any report artifacts for that invocation.
- If the command fails with exit code `3` after reaching this eligibility point due to `PATH` being unreadable or unparsable, the command MUST write exactly one validation report for that invocation, MUST record a `blocking` finding for `PATH` with an appropriate IO/parser failure category, and MUST NOT write a confidence report.
- If the command fails with exit code `2` after reaching this eligibility point due to any deterministic configuration/precondition failure (including but not limited to: required artifact missing/schema-invalid, localization ID collision, authoritative-role conflicts, multiple authoritative inventory entries, or immutable-field violations), the command MUST write exactly one validation report for that invocation, MUST NOT attempt any provider calls, and MUST NOT write a confidence report.
- For report-eligible invocations, the command MUST prepare exactly one validation report in memory and persist it only as part of the atomic commit step; if any staging or commit step fails (including report persistence failure), the command MUST exit with code `3` and no report is written.
- If `--confidence-mode` is omitted and `context-anchor.yaml` exists but is schema-invalid (evaluated only after eligibility is met), the invocation is still report-eligible and MUST write the validation report, but MUST set the outcome exit code to `2` and MUST NOT write a confidence report.

Report artifacts (MVP):

- The command MUST write a validation report under `<resolved --report-dir>/validation/` whenever the invocation is validation-report-eligible.
- If the command writes a confidence report, it MUST write it under `<resolved --report-dir>/confidence/`.

Managed artifact mutation rules (inventory, MVP):

- This command may update `inventory.yaml`.
- This command MUST NOT modify any localization files.
- If `--role target` (default), the command MUST NOT modify `parley.yaml` or `canonical-inventory.json`.
- If `--role authoritative`:
  - If an authoritative entry already exists and it is not the same inventory record as the record being added/updated (i.e., it has a different `localization_id`), the command MUST fail with exit code `2` and MUST NOT modify `inventory.yaml`, `parley.yaml`, or `canonical-inventory.json`.
  - If an authoritative entry already exists and it is the same inventory record as the record being added/updated, the command MAY update only the allowed metadata fields on that record but MUST keep its `role=authoritative` and MUST apply field-level immutability rules below.
  - If no authoritative entry exists, the command MUST set the added/updated record's `role=authoritative`.
- If and only if the command completes successfully with the project having a single authoritative inventory entry (whether it existed already or was just created), the command MUST ensure authoritative-derived artifacts are coherent:
  - `parley.yaml` MUST reference the authoritative inventory record's `localization_id` as the project's authoritative localization.
  - `canonical-inventory.json` MUST be regenerated deterministically from the authoritative localization file.
  - If regeneration cannot complete due to read/write or parser failure, the command MUST fail with exit code `3`.

Allowed inventory field updates (MVP):

- When `parley localization add` resolves to an update of an existing inventory record (same `localization_id`) the command MUST treat inventory updates as a closed set of field mutations.
- If the invocation attempts to change an immutable field, the command MUST fail with exit code `2` and MUST NOT modify `inventory.yaml`, `parley.yaml`, or `canonical-inventory.json`. If the invocation is validation-report-eligible (as defined above), it MUST still write its validation report for this invocation, but MUST NOT attempt any provider calls and MUST NOT write a confidence report.
- Mutability is defined per field as follows:

| Field | Mutable? | Update rule (MVP) |
| --- | --- | --- |
| `localization_id` | no | Immutable. The record being updated is selected by `localization_id`. |
| `path` | no | Immutable. `PATH` MUST canonicalize to the existing record `path` under the same project-root-relative canonicalization rule. |
| `locale` | no | Immutable. The normalized `--locale` MUST equal the existing record `locale`. |
| `format` | yes | May be updated only if (a) the invocation explicitly provides `--format`, and (b) `PATH` parses successfully under the resulting format. |
| `role` | conditional | If `--role target`, the record `role` MUST remain unchanged. If `--role authoritative`, the record `role` MUST be `authoritative`. |
| `status` | yes | May be updated to the provided `--status` value; if omitted, status MUST remain unchanged. |

Notes:

- The immutability of `path` and `locale` ensures that two implementations cannot “retarget” an existing record via `parley localization add`; retargeting (if ever allowed) is a separate post-MVP workflow.

Atomicity (MVP):

- This command may update multiple managed artifacts (`inventory.yaml` and, when authoritative coherence applies, `parley.yaml` and `canonical-inventory.json`).
- In the MVP, these atomicity/rollback guarantees are defined only for normal command completion (the process returns an exit code). Crash/power-loss recovery is out of scope for the MVP; a crash may leave staged files or a partially-committed final state.
- If the command exits with code `3`, it MUST leave `inventory.yaml`, `parley.yaml`, and `canonical-inventory.json` unchanged from their pre-invocation contents (no partial updates).
- If the command exits with code `3`, it MUST NOT leave any new report artifacts for this invocation under the resolved `--report-dir` (no partially written validation/confidence report files).

Operation order and commit point (MVP):

- For a valid invocation, the command MUST apply the following deterministic operation order:
  1. Resolve `<project-root>`, resolve the report root (`--report-dir`), and canonicalize `PATH` using the project-root-relative path rule used for stable localization ID derivation.
  2. Resolve the effective parser format for `PATH` using the global parser format resolution rules.
     - If `--format` is omitted, the command MUST treat rule (1) (inventory-based format selection) as applicable only if `inventory.yaml` is present and schema-valid. If `inventory.yaml` is missing or schema-invalid, rule (1) MUST be treated as non-matching and the command MUST proceed to extension-based inference.
  3. Verify `PATH` is readable and parseable under the resolved format.
     - If the file cannot be read, the command MUST fail with exit code `3` after eligibility is met, MUST write the validation report, and MUST NOT write a confidence report.
     - If the file cannot be parsed under the resolved format (including format/content mismatch), the command MUST fail with exit code `3` after eligibility is met, MUST write the validation report, and MUST NOT write a confidence report.
  4. Determine required artifacts for this invocation (`inventory.yaml`, `canonical-inventory.json`, and conditionally `parley.yaml` and `context-anchor.yaml`) and check missing/schema-invalid status.
  5. Resolve whether this invocation is an add or an update by determining the effective `localization_id`.
  6. If authoritative coherence applies, prepare updated `parley.yaml` and regenerated `canonical-inventory.json` in memory (or in staged files outside final paths).
  7. Prepare the validation report in memory (and confidence report, if applicable) using the required report envelope.
  8. If any deterministic configuration/precondition failure sets the outcome exit code to `2`, the command MUST NOT stage any managed artifact mutations, but MUST still persist the validation report (and MUST NOT persist a confidence report).
  9. Otherwise, stage all file writes outside their final paths, including `inventory.yaml` (and, when authoritative coherence applies, `parley.yaml` and `canonical-inventory.json`) and all required report files.
  10. Atomically commit the staged writes by replacing managed artifact files and adding the report artifacts.

Rollback on commit failure (MVP):

- If any atomic commit step fails after it begins:
  - The command MUST attempt to rollback:
    - Restore already-replaced managed files (`inventory.yaml`, `parley.yaml`, and `canonical-inventory.json` when applicable) from their pre-invocation copies in reverse commit order.
    - Remove any newly-created managed files in the commit unit.
    - Remove the validation report and confidence report for this invocation if either was already placed at its final path.
  - Remove or ignore all pending staged/temp files for this invocation.
  - Exit with code `3` whether rollback succeeds or fails.
- If rollback itself fails, the command MUST still report the invocation as failed with exit code `3`; it MUST NOT attempt a second commit, and MUST NOT treat the invocation as a validation success.

Exit behavior (MVP):

- If validation produces one or more blocking findings and the atomic commit succeeds, the command MUST exit with code `1`.
- Otherwise (no blocking findings) and the atomic commit succeeds, the command MUST exit with code `0`.

## 7. Validation Commands

### 7.1 `parley validate`

Validates project-managed localization artifacts and writes a validation report after validation targets have been selected.

```text
parley validate [--only LOCALE] [--targets|--no-targets] [--authoritative|--no-authoritative]
```

Options (MVP):

| Option | Type | Required | Description |
| --- | --- | --- | --- |
| `--only LOCALE` | BCP 47 string | no | Restrict validation to inventory entries whose normalized `locale` matches. |
| `--targets` / `--no-targets` | boolean flag pair | no | Include target inventory entries; default is `--targets`. |
| `--authoritative` / `--no-authoritative` | boolean flag pair | no | Include the authoritative inventory entry (when one exists); default is `--authoritative`. |

Validation target selection (MVP):

- The command MUST resolve `<project-root>` using global project-root resolution rules.
- The command MUST read and schema-validate `inventory.yaml`.
  - If `inventory.yaml` is missing or schema-invalid, the command MUST fail with exit code `2` before selected localization entries exist and MUST NOT write a validation report.
- After selected localization entries exist, the command MUST require and schema-validate `canonical-inventory.json` before any per-entry structural or placeholder integrity validation.
  - If `canonical-inventory.json` is missing or schema-invalid, the command MUST fail with exit code `2` and MUST still write exactly one validation report for the invocation (subject to normal report-write failure precedence). The report MUST include at least one `blocking` finding with `category=artifact_schema` and `failure_category=missing|required_artifact_schema_invalid` as appropriate.
- The command MUST determine the authoritative inventory entry using the authoritative role semantics described in 6.1.
  - If the inventory contains more than one authoritative entry, the command MUST fail with exit code `2` before selected localization entries exist and MUST NOT write a validation report.
- The command MUST select which inventory entries to validate deterministically from:
  - The authoritative entry (when `--authoritative` is in effect and one exists).
  - All target entries (when `--targets` is in effect).
  - If `--only LOCALE` is provided, the command MUST filter the selected entries to those whose `locale` equals the normalized `--only` value.
- If the resulting selected entry set is empty after applying `--targets/--no-targets`, `--authoritative/--no-authoritative`, and optional `--only` filtering, the command MUST fail with exit code `2` before selected localization entries exist and MUST NOT write a validation report.
- The command MUST establish a deterministic selected-entry processing order before any per-entry file reads or parses:
  - After selection and optional `--only` filtering, the command MUST sort the selected entries by the tuple `(locale, path, localization_id)` ascending.
  - The command MUST process selected entries in exactly this order.
  - When the command halts on the first failing selected entry (missing/unreadable/parser failure), the halt point MUST be the first failing entry in this deterministic order.

Validation report eligibility (MVP):

- Validation report persistence requirements apply only after selected localization entries exist.
- If the command fails with exit code `2` before selected localization entries exist (for example: missing/schema-invalid `inventory.yaml`, multiple authoritative entries, invalid `--only` filter that yields empty selection), the command MUST NOT write any validation report.
- After selected localization entries exist, the command MUST write exactly one validation report under `<resolved --report-dir>/validation/` using the shared report naming and minimal envelope rules.
- If the command fails with exit code `3` after selected localization entries exist due to an IO or parser failure for a selected localization file, the command MUST still write exactly one validation report for that invocation (subject to report-write failure precedence). It MUST record the IO/parser failure as a `blocking` finding for that selected entry.

Validation behavior (MVP):

- The command MUST validate each selected inventory entry in processing order.
- If a selected entry is missing, unreadable, or unparsable, the command MUST:
  - Record the entry as `missing|io_error|parse_error` in `validated_localizations`.
  - Record at least one `blocking` finding for that entry.
  - Halt validation at the first failing entry and proceed to report writing.
- For selected entries that are successfully parsed, the command MUST perform local structural and placeholder integrity validation and add corresponding findings.

Validation report requirements (MVP):

- The command MUST NOT write a validation report for failures that occur before selected localization entries exist.
  - This no-report rule applies to missing or schema-invalid `inventory.yaml`, multiple authoritative inventory entries, invalid `--only LOCALE` before filtering, and any other pre-selection configuration failure.
  - These failures MUST use their normal exit status (`2` for usage/configuration or schema failures, `3` for parser/IO failures) and MUST NOT create a partial report artifact.
- After selected localization entries exist, the command MUST write exactly one validation report under `<resolved --report-dir>/validation/` using the shared report naming and minimal envelope rules.
- The report MUST include a required array `validated_localizations`, in stable order by `(locale, path, localization_id)` ascending, containing objects with:
  - `localization_id`
  - `locale`
  - `path`
  - `format`
  - `status` with a closed enum value: `validated|missing|io_error|parse_error`
- The report MUST include a required array `findings`, which MAY be empty.

Exit behavior (MVP):

- If the command fails with exit code `2` after selected localization entries exist (for example missing or schema-invalid `canonical-inventory.json`), and report writing succeeds, the command MUST exit with code `2`.
- Otherwise, if validation halts due to a selected entry being `missing`, `io_error`, or `parse_error`, and report writing succeeds, the command MUST exit with code `3`.
- Otherwise, if validation produces one or more `blocking` findings for any selected entry and report writing succeeds, the command MUST exit with code `1`.
- Otherwise, if report writing succeeds, the command MUST exit with code `0`.

## 8. Translation Commands

### 8.1 `parley translate`

Translates from the project's authoritative localization into a target localization in project mode.

```text
parley translate --target-locale LOCALE [--target-path PATH] [--dry-run] [--reuse-mode tm_only|tm_then_provider|provider_only]
```

Project-mode requirement (MVP):

- This command is project-mode only: it MUST require a valid `<project-root>` and Parley project artifacts.
- Paired-file translation (non-project) is deferred post-MVP and is not part of this command surface.

Options (MVP):

| Option | Type | Required | Description |
| --- | --- | --- | --- |
| `--target-locale LOCALE` | BCP 47 string | yes | Target locale to translate into. |
| `--target-path PATH` | path | no | Target file path override under `<project-root>`. In the MVP, this option MUST NOT create new inventory entries; if provided, it MUST match the resolved target inventory entry `path`. |
| `--dry-run` | boolean | no | When true, MUST NOT modify any managed artifacts. Reports MUST still be written. |
| `--reuse-mode tm_only|tm_then_provider|provider_only` | enum | no | Defaults to `tm_then_provider`. Controls whether the command may reuse translation memory and/or call a provider. |

Preconditions (MVP):

- The command MUST read and schema-validate `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `translation-memory.sqlite`, and `context-anchor.yaml`.
  - If any required artifact is missing or schema-invalid, the command MUST fail with exit code `2`.
- The command MUST attempt to read and schema-validate `glossary.yaml`.
  - If `glossary.yaml` is missing, the command MUST behave as if an empty ruleset is present (no terminology constraints).
  - If `glossary.yaml` is present but schema-invalid, the command MUST fail with exit code `2`.
- The command MUST load the canonical key list/order from validated `canonical-inventory.json`; this order is the canonical-key order used for per-key evaluation and report writing.
- The command MUST resolve the authoritative inventory entry.
  - If there is no authoritative entry, the command MUST fail with exit code `2`.

Localization format resolution for translate (MVP):

- The command MUST use inventory-declared formats (not extension inference) for translation parse/write behavior:
  - Parse the authoritative localization file using the resolved authoritative inventory entry `format`.
  - Parse (if present) and write the target localization file using the resolved target inventory entry `format`.
- If either resolved inventory entry has a missing or unsupported `format`, the command MUST fail with exit code `2` before attempting to parse the corresponding localization file.
- If parsing fails under the resolved format (including format/content mismatch), the command MUST fail with exit code `3` with `failure_category=source_parse_error` or `failure_category=target_parse_error` as appropriate.

- The command MUST enforce the project-mode context anchor requirement before any provider calls:
  - `context-anchor.yaml` MUST contain populated per-key context for project-mode translation.
  - A context anchor that is schema-valid but effectively empty or unpopulated for translation MUST be treated as an error.
  - For MVP determinism, “populated per-key context” means: for every canonical key present in validated `canonical-inventory.json`, the context anchor MUST provide a non-empty (after trimming whitespace) context value for that key.
  - If this requirement is not met, the command MUST fail fast with exit code `2` and MUST NOT perform any provider calls or stage any managed-artifact mutations.
- The command MUST resolve exactly one target inventory entry for the normalized `--target-locale` deterministically.
  - The candidate set is all inventory entries with `role=target` whose `locale` equals the normalized `--target-locale`.
  - If the candidate set is empty, the command MUST fail with exit code `2`.
  - If the candidate set contains exactly one entry, that entry is the resolved target.
    - If `--target-path` is provided, the command MUST canonicalize `--target-path` to a project-relative path using the same canonicalization rules used for localization IDs, and MUST fail with exit code `2` if the canonicalized `--target-path` does not exactly equal the resolved target inventory entry `path`.
  - If the candidate set contains more than one entry:
    - If `--target-path` is omitted, the command MUST fail with exit code `2`.
    - Otherwise, the command MUST select the entry whose `path` matches the canonicalized project-relative `--target-path`.
    - If no entry matches, the command MUST fail with exit code `2`.

Translation report eligibility (MVP):

- Translation report persistence requirements apply only after the command has successfully:
  - Resolved `<project-root>`.
  - Schema-validated `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `translation-memory.sqlite`, and `context-anchor.yaml`.
  - Loaded glossary rules from `glossary.yaml` (or treated it as an empty ruleset when missing).
  - Resolved the authoritative inventory entry.
  - Resolved the target inventory entry (including validating `--target-path` match when provided).
- If the command fails with exit code `2` before reaching this eligibility point due to missing/schema-invalid artifacts, missing authoritative entry, target entry resolution failure (including `--target-path` mismatch), or context anchor precondition failure, the command MUST NOT write any translation report.
- For report-eligible invocations, if the command later fails with exit code `2` for specific post-eligibility deterministic artifact-consistency cases (`source_missing`, `tm_current_conflict`, and provider-disallowed mapping), it MUST still write exactly one translation report.
- If the command fails with exit code `3` after reaching this eligibility point due to authoritative localization IO or parser failure while attempting to load/parse the authoritative localization file, the command MUST write exactly one translation report for that invocation, MUST NOT attempt any provider calls or write-back, and MUST set `failure_category=source_io_error|source_parse_error` as appropriate.

Provider classification for this command (MVP):

- Provider-backed work is controlled by `--reuse-mode`:
  - `tm_only`: provider-backed work is `not_applicable` (the command MUST NOT perform any provider calls).
  - `tm_then_provider`: provider-backed work is required if and only if at least one key cannot be satisfied by translation-memory reuse (and is not `skipped`).
  - `provider_only`: provider-backed work is required for any key that is not `skipped`.
- If provider-backed work is required for the invocation and `--no-provider` is set, the command MUST fail fast with exit code `2` and MUST NOT perform any provider calls.

Translate provider/report closed mapping (MVP):

The following table closes translation-report persistence and `provider_status` mapping for all MVP required-provider outcome paths.

- For report-eligible invocations (as defined above), in all rows, the command MUST write exactly one translation report under `<resolved --report-dir>/translation/` unless report persistence fails (in which case the command MUST exit with code `3` per exit-code precedence).

| Scenario | Provider required for invocation? | Provider calls attempted? | Exit code | Translation report | `provider_status` mapping | `per_key_outcomes` behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `--reuse-mode=tm_only` | no (`not_applicable`) | no | `0` or `1` (per non-provider outcomes) | written | `provider_status=not_applicable` | Full array in canonical-key order; outcomes from ladder (no `generated`). |
| `--reuse-mode=tm_then_provider` or `provider_only`, but no key reaches tentative `generated` after ladder evaluation | no | no | `0` or `1` (per non-provider outcomes) | written | `provider_status=skipped`, `provider_skip_reason=not_needed` | Full array in canonical-key order; outcomes are `skipped|reused|failed` only. |
| Provider required and `--no-provider` is set | yes | no | `2` | written | `provider_status=skipped`, `provider_skip_reason=no_provider` | Full array in canonical-key order; any key that would reach `generated` MUST instead be `failed` with report category `provider_disallowed`. |
| Provider required and provider is unavailable before any provider call is attempted | yes | no | `4` | written | `provider_status=failed`, `provider_failure_category=unavailable` | First key whose outcome would be `generated` MUST be `failed` with report category `provider_failed`; later keys follow the post-failure rule (`provider_not_attempted_after_failure` when they would reach `generated`). |
| Provider required and provider becomes unavailable on the first provider call | yes | yes (attempted) | `4` | written | `provider_status=failed`, `provider_failure_category=unavailable` | First key whose outcome would be `generated` MUST be `failed` with report category `provider_failed`; later keys follow the post-failure rule (`provider_not_attempted_after_failure` when they would reach `generated`). |
| Provider required and provider fails or returns invalid required output during generation | yes | yes | `4` | written | `provider_status=failed`, `provider_failure_category=error|invalid_output` as appropriate | First provider-failed key MUST be `failed` with report category `provider_failed`; later keys follow the post-failure rule (`provider_not_attempted_after_failure` when they would reach `generated`). |
| Provider required and all required provider calls succeed | yes | yes | `0` or `1` (per non-provider outcomes) | written | `provider_status=used` | Full array in canonical-key order; keys may be `generated` where provider was used. |

Per-key outcome model (MVP):

- For each canonical key present in the authoritative localization, the command MUST assign exactly one per-key outcome in a closed enum:
  - `skipped`: the key was not modified in the target localization (for example unchanged, locked, or approved by policy).
  - `reused`: the target value was reused from translation memory without calling a provider for that key.
  - `generated`: the target value was generated (or regenerated) via provider-backed work for that key.
  - `failed`: the key could not be translated for this invocation.
- Failure causes (MVP):
  - If `--reuse-mode=tm_only` and no eligible translation-memory reuse winner exists for a key, that key MUST be assigned outcome `failed`.
  - If provider-backed work is required for a key and the provider fails or returns invalid required output for that key, that key MUST be assigned outcome `failed`.
- Outcome-to-exit mapping (MVP):
  - If any key outcome is `failed` due to required provider-backed work failure, the command MUST exit with code `4` (after attempting to write the translation report).
  - Otherwise, if any key outcome is `failed` (including `tm_only` misses), the command MUST exit with code `1` (after attempting to write the translation report).

Canonical key decision ladder (MVP):

- The command MUST evaluate canonical keys in the stable canonical-key order defined by `canonical-inventory.json`.
- Before assigning per-key outcomes, the command MUST classify each canonical key's inputs:
  - If the canonical key is present in `canonical-inventory.json` but missing from the parsed authoritative localization, the project artifacts are inconsistent; the command MUST fail with exit code `2` before provider calls or write-back and MUST write a translation report with `failure_category=source_missing`.
  - If the target localization file exists but cannot be read under the resolved target format, the command MUST fail with exit code `3` before provider calls or write-back, and MUST write a translation report with `failure_category=target_io_error`.
  - If the target localization file exists but cannot be parsed under the resolved target format (including format/content mismatch), the command MUST fail with exit code `3` before provider calls or write-back, and MUST write a translation report with `failure_category=target_parse_error`.
  - If the target localization file is missing, the command MUST treat every canonical key as having no existing target value; this is not by itself a failure.
  - If the target localization file exists but lacks a value for a canonical key, that key has no existing target value; this is not by itself a failure.
  - If translation memory has two or more records marked `is_current=true` for the key's conflict identity, translation memory is invalid; the command MUST fail with exit code `2` before provider calls or write-back and MUST write a translation report with `failure_category=tm_current_conflict`.
- For each canonical key after input classification, the command MUST choose the first matching path below and MUST NOT evaluate later paths for that key. When glossary rules are present, provider-backed generation MUST apply the glossary terminology constraints for the target locale (and MUST treat provider output that violates blocking glossary constraints as `invalid_output` provider failure for that key):
  1. `skipped` with report category `unchanged`: an existing target value is present, the selected current translation-memory record has `last_translated_source_hash` equal to the current authoritative `content_hash`, and that record's `target_value` exactly equals the existing target value.
  2. `skipped` with report category `human_status_preserved`: the selected current translation-memory record has `human_status` of `locked` or `approved`, and that record's `target_value` exactly equals the existing target value.
  3. `failed` with report category `target_tm_conflict`: the selected current translation-memory record has `human_status` of `locked` or `approved`, but the existing target value is missing or differs from that record's `target_value`.
  4. `reused`: `--reuse-mode` is `tm_only` or `tm_then_provider`, and a deterministic eligible translation-memory reuse winner exists under the reuse ordering below. The reused target value is the winner's `target_value`.
  5. `generated`: `--reuse-mode` is `tm_then_provider` or `provider_only`. Provider generation is required for this key, and the generated target value is determined by the provider response if the provider succeeds.
  6. `failed` with report category `tm_miss`: `--reuse-mode` is `tm_only` and no eligible reuse winner exists.
- Provider-backed work is required for the invocation if and only if one or more keys are assigned the tentative path `generated`.
- If provider generation is attempted and fails for a key:
  - That key's final outcome MUST be `failed` with report category `provider_failed`.
  - The command MUST NOT attempt any provider calls for later keys in the canonical-key order.
  - The command MUST still produce one `per_key_outcomes` entry for every canonical key (including keys after the failed provider call) in the stable canonical-key order.
  - For keys after the first provider failure, the command MUST continue evaluating the canonical key decision ladder deterministically with provider calls disallowed:
    - If the ladder resolves the key as `skipped` or `reused` without requiring provider calls, the command MUST record that outcome.
    - If the ladder would reach path `generated` for the key, the command MUST instead set outcome `failed` with report category `provider_not_attempted_after_failure`.
- The translation report's `per_key_outcomes` entries MUST include `key`, `outcome`, and, when outcome is `skipped` or `failed`, the required failure/skip category named above. This is the MVP required-field surface; no exhaustive diagnostic schema is required.

Deterministic reuse ordering (MVP):

- When `--reuse-mode` permits translation memory reuse and there are multiple eligible translation memory records for the same conflict identity, the command MUST select a winner deterministically by sorting candidate records by this stable tuple (ascending unless noted):
  - `human_status` rank (higher priority first): `approved` > `reviewed` > `draft` (treat unknown as lowest).
  - `provenance` rank (higher priority first): `human_approved` > `human_reviewed` > `machine_generated` > `imported` (treat unknown as lowest).
  - `updated_at` (newer first).
  - `tm_record_id` (lexical).
- The reuse winner MUST be the first record in this sorted order.

Report requirements (translation, MVP):

- The translation report MUST be written under `<resolved --report-dir>/translation/`.
- The report MUST include required fields:
  - `target_locale`
  - `target_path` (the resolved target inventory entry `path`)
  - `reuse_mode`
  - `provider_status` (plus conditional provider fields per global Provider status reporting)
  - `failure_category` when the exit code is `2`, `3`, or `4`
  - `per_key_outcomes` array in canonical-key order
- `failure_category` closed enum values (MVP):
  - `source_io_error`
  - `source_parse_error`
  - `source_missing`
  - `target_io_error`
  - `target_parse_error`
  - `tm_current_conflict`
  - `provider_disallowed`
  - `provider_failed`
  - `blocking_validation_findings`
- When the command exits with code `2` because provider work is required but disallowed by `--no-provider`, the translation report MUST set `failure_category=provider_disallowed`.

Write-back rules (target localization, MVP):

- If `--dry-run` is true, the command MUST NOT write the target localization file.
- If `--dry-run` is false:
  - The command MUST stage and atomically write a complete updated target localization file (not incremental in-place edits).
  - The command MUST NOT write the updated target localization file until after it has fully evaluated all canonical keys and prepared the translation report.

Validation of staged result (MVP):

- After generating or reusing translations and staging the resulting target localization content, the command MUST run local structural and placeholder integrity validation on the staged result before committing write-back.
- If this staged validation yields one or more `blocking` findings:
  - The command MUST still write exactly one translation report.
  - The command MUST NOT write back the staged target localization file.
  - The command MUST exit with code `1`.
  - The report MUST include `failure_category=blocking_validation_findings`.
  - The report MUST include a required array `validation_findings` containing at least all `blocking` findings produced by this staged validation step.
    - The finding shape is owned by `07-validation-error-taxonomy-spec.md`.
    - The `validation_findings` array MUST be sorted deterministically using the same stable tuple defined for validation reports in section 4.

Atomicity, commit unit, and rollback (MVP):

- This command may persist multiple durable artifacts: updated target localization write-back, `translation-memory.sqlite` mutations, and the translation report.
- In the MVP, these atomicity/rollback guarantees are defined only for normal command completion (the process returns an exit code). Crash/power-loss recovery is out of scope for the MVP; a crash may leave staged files or a partially-committed final state.
- Commit units:
  - If `--dry-run` is true, the commit unit is the translation report only.
  - If the staged-result validation produces one or more `blocking` findings, the commit unit is the translation report only (no target write-back and no translation-memory mutation).
  - Otherwise (`--dry-run` is false and staged-result validation produced no `blocking` findings), the commit unit is:
    - Target localization file write-back.
    - `translation-memory.sqlite` updates (per Translation memory write-back rules).
    - Translation report file under `<resolved --report-dir>/translation/`.
- Commit order:
  - The command MUST stage all file writes outside their final paths for every artifact in the commit unit.
  - The command MUST atomically commit the staged writes in deterministic order:
    1. Target localization file write-back.
    2. `translation-memory.sqlite`.
    3. Translation report.
- Rollback on commit failure:
  - If any atomic commit step fails after it begins:
    - The command MUST attempt to rollback the entire commit unit:
      - Restore any already-replaced files in reverse commit order to their exact pre-invocation contents.
      - Remove any newly-created files placed at their final paths.
    - Remove or ignore all pending staged/temp files for this invocation.
    - Exit with code `3` whether rollback succeeds or fails.
  - If rollback itself fails, the command MUST still report the invocation as failed with exit code `3`; it MUST NOT attempt a second commit, and MUST NOT treat the invocation as successful.

Exit behavior (MVP):

- If any staging or commit step fails (including report persistence or any required write-back), the command MUST exit with code `3`.
- Otherwise, if required provider-backed translation fails for any key, the command MUST exit with code `4`.
- Otherwise, if any key has per-key outcome `failed`, the command MUST exit with code `1`.
- Otherwise, if validation of the staged resulting target localization produces one or more `blocking` findings, the command MUST exit with code `1`.
- Otherwise, the command MUST exit with code `0`.

Deterministic `tm_record_id` derivation (MVP):

- The deterministic `tm_record_id` derivation rule is defined by `08-translation-memory-spec.md`.
- When translation memory write-back requires selecting or creating a `tm_record_id` for a `generated` outcome, the CLI MUST provide the derivation inputs required by that leaf spec, including at minimum:
  - Conflict identity `(key, authoritative source locale, target locale)`
  - The current authoritative `content_hash` (as `source_content_hash`)
  - The resulting `target_value` to be recorded

Translation memory write-back rules (MVP):

- These rules apply only when all of the following are true:
  - The translation run produced no blocking findings.
  - `--dry-run` is false.
  - All required provider calls (if any) completed successfully.
- The command MUST NOT mutate translation memory for keys whose per-key outcome is `skipped` (unchanged, locked, or approved).
- For each canonical key whose per-key outcome is `reused` or `generated`, the command MUST update translation memory for the conflict identity `(key, authoritative source locale, target locale)` deterministically as follows:
  - The command MUST set exactly one record to `is_current=true` for the conflict identity: the record whose `tm_record_id` was selected for the key in the run.
    - For `reused`, this is the `tm_record_id` of the deterministic reuse winner.
    - For `generated`, this is the deterministic `tm_record_id` derived by the `tm_record_id` derivation rule defined by `08-translation-memory-spec.md` (and therefore identifies exactly one inserted-or-updated record).
  - The command MUST set `is_current=false` on all other records for the conflict identity.
  - The record selected as current MUST store the current authoritative `content_hash` as its `source_content_hash`.
  - The record selected as current MUST store a field named `last_translated_source_hash` equal to the current authoritative `content_hash`.
  - If the per-key outcome is `reused`:
    - The command MUST NOT modify `target_value`, `human_status`, or `provenance` of the reused record.
    - The command MAY update `updated_at` if and only if the record required a change to become the sole `is_current=true` record or its `last_translated_source_hash` field changed. When it updates `updated_at`, it MUST set it to this invocation's translation report `started_at` value exactly (UTC RFC 3339 with microseconds: `YYYY-MM-DDTHH:MM:SS.ffffffZ`).
  - If the per-key outcome is `generated`:
    - The command MUST insert a new record with a new stable unique `tm_record_id`, using the deterministic `tm_record_id` derivation rule defined by `08-translation-memory-spec.md`.
    - If a record with the derived `tm_record_id` already exists for the conflict identity, the command MUST NOT insert a second record; it MUST update and mark that existing record as current under the rules above.
    - The inserted (or reused) record MUST have: `is_current=true`, `source_content_hash` equal to the current authoritative `content_hash`, `last_translated_source_hash` equal to the current authoritative `content_hash`, `target_value` equal to the generated value written to the target localization, `provenance=machine_generated`, and `human_status=draft`.
    - The inserted (or reused) record MUST set `updated_at` to this invocation's translation report `started_at` value exactly (UTC RFC 3339 with microseconds: `YYYY-MM-DDTHH:MM:SS.ffffffZ`).

## 14. Leaf Spec Linkage

This CLI spec depends on the following leaf specs for detailed schemas/enums/contracts:

- `02-project-artifact-schema-spec.md`: Project artifacts and report schemas.
- `03-parser-interface-format-spec.md`: Parser adapters, parser output shape, and format-specific rules.
- `07-validation-error-taxonomy-spec.md`: Validation categories, finding shapes, failure categories, and severity definitions.
- `08-translation-memory-spec.md`: Translation memory record schemas, `tm_record_id` derivation, and current-record mutation semantics.

This CLI spec is the authority for the command surface, option behavior, and exit code mapping.

## 15. Initial Implementation Milestones

1. Build the CLI skeleton, project manifest, inventory, and canonical inventory.
2. Implement parser abstraction with iOS `.strings` and Android XML adapters.
3. Implement structural comparison and placeholder extraction/validation.
4. Add project initialization and localization add workflows.
5. Add report writer and CI-friendly exit codes.
6. Add context-anchor storage and standalone confidence report generation.
7. Add glossary validation.
8. Add translation memory.
9. Add context-aware incremental translation generation.
10. Add semantic comparison workflows.

## 16. MVP Architecture Acceptance Criteria

This CLI Command Specification is “done enough” for MVP implementation when the following observable checks hold:

- **Project init artifacts (5.1):** `parley project init` produces `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, and a schema-valid empty `context-anchor.yaml` placeholder, plus an initialization report.
- **Add-localization artifacts (6.1):** For validation-report-eligible invocations in project mode, `parley localization add` emits a validation report that includes canonical-inventory structural baseline findings (missing/extra keys and placeholder-signature mismatches). When `--confidence-mode` resolves to `anchor` or `standalone` and the outcome exit code is `0` or `1`, it also emits a confidence report; mode selection and provider-skipped behavior follow the rules in 6.1 (no silent ambiguity between standalone vs relative-to-anchor).
- **Command output/failure completeness:** Each MVP command defined in sections 5–8 names its terminal outputs (artifacts/reports) and at least one obvious failure category (e.g., parser/IO, artifact schema invalid, provider required/unavailable, blocking validation findings).
- **Authority alignment:** This leaf spec defines the command surface, required artifact/report write locations, and exit behavior; the HLD remains the architecture authority for authoritative-producer/mutation boundaries, and detailed schemas/enums/contracts are owned by the leaf specs listed in section 14.
- **Project-scoped reports:** MVP report outputs are written under the resolved `--report-dir` (which MUST remain under `<project-root>/reports/`), are run-scoped by default, and do not silently overwrite prior reports.
- **Deferred paired translation (8.1):** Paired-file translation is explicitly marked post-MVP and is not part of `parley translate`; it does not define MVP report-root, overwrite, or write-back requirements.
- **Leaf-spec linkage:** Detailed schema/enums/contracts referenced by this CLI spec are owned by the appropriate leaf specs in section 14 (the HLD remains architectural and does not expand full report/validation/confidence schemas).
