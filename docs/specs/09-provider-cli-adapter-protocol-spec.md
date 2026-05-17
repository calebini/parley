# Provider CLI Adapter Protocol Specification

## 1. Scope

This specification defines the MVP protocol between Parley and command-line LLM provider tools such as Codex CLI, Claude CLI, or a deterministic fake provider CLI used in tests.

The protocol covers:

- Provider CLI process invocation.
- Translation request and response JSON envelopes.
- Schema validation of provider output.
- Timeout, process failure, invalid-output, and refusal behavior.
- Provider telemetry captured by Parley.
- Mapping provider failures into Parley translation outcomes and reports.

This spec does not define prompt quality, translation memory lookup, placeholder extraction, glossary semantics, or parser write-back. Those remain owned by the Translation Workflow, Translation Memory, Placeholder Integrity, Parser Interface, and CLI Command specs.

Architecture authority for MVP boundaries is the Parley High-Level Design (HLD). The v1 spec index is dependency/navigation context only.

## 2. Dependencies

This spec depends on:

- [CLI Command Specification](01-cli-command-spec.md)
- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Placeholder and Token Integrity Specification](04-placeholder-token-integrity-spec.md)
- [Translation Workflow Specification](06-translation-workflow-spec.md)
- [Validation and Error Taxonomy Specification](07-validation-error-taxonomy-spec.md)
- [Translation Memory Specification](08-translation-memory-spec.md)

## 3. Adapter Boundary

Parley MUST treat provider-backed translation as a structured command invocation, not as unstructured terminal text.

The reusable adapter layer owns:

- Command construction.
- Working directory selection.
- Request JSON delivery.
- Timeout enforcement.
- stdout/stderr capture.
- Process exit-code capture.
- JSON object extraction from provider output.
- Response schema validation.
- Provider telemetry capture.

The Parley translation layer owns:

- Which keys require provider generation.
- Request entry construction.
- Prompt/context content.
- Placeholder sentinel preparation and restoration.
- Glossary and translation-memory inputs.
- Mapping validated provider entries back to canonical keys.
- Translation report and write-back behavior.

Provider-specific adapters MAY wrap different CLIs, but all provider-specific adapters MUST return the same normalized Parley provider response shape to the translation layer.

## 4. Provider Configuration

An MVP provider CLI configuration MUST include:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `provider_id` | string | yes | Stable provider adapter ID, e.g. `codex-cli`, `claude-cli`, `fake-cli`. |
| `command` | string | yes | Executable name or absolute executable path. If not absolute, resolved via PATH lookup rules (Section 5.2). |
| `args` | array of strings | no | Static arguments supplied before Parley request delivery. |
| `timeout_seconds` | integer | yes | Per invocation timeout in seconds. MUST be a positive integer greater than zero. |
| `cwd` | string | no | Working directory. If omitted, use the project root. If relative, resolve relative to the project root. |
| `request_delivery` | string | yes | One of `stdin_json`, `stdin_prompt`, `argument_prompt`, or `output_file`. |
| `response_mode` | string | yes | One of `stdout_json`, `stdout_json_envelope`, or `output_file_json`. |
| `io_dir` | string | no | Directory used for transient request/response transport files when `request_delivery=output_file` and/or `response_mode=output_file_json`. If relative, resolve relative to `cwd`. Default `.parley/provider-io`. Transport files are not Parley artifacts and MUST be cleaned up per Section 5.1. |

MVP implementations MAY hard-code provider configurations while the command surface is still small. Once provider configuration is user-facing, invalid provider configuration MUST be classified as usage/configuration failure with exit code `2` before provider invocation.

## 5. Process Invocation Rules

Parley MUST invoke provider CLIs as child processes with:

- A deterministic working directory.
- A deterministic request payload.
- A finite timeout.
- Captured stdout and stderr.

Timeout validation (MVP):

- Before provider invocation, the adapter MUST validate `timeout_seconds`.
- Missing, non-integer, zero, or negative `timeout_seconds` MUST be treated as invalid usage/configuration and MUST fail with exit code `2` before provider invocation.

### 5.0 Working Directory Resolution (MVP)

Before provider invocation, the adapter MUST resolve the provider configuration `cwd` into an absolute `resolved_cwd` used as the process working directory and as the base for resolving any relative `io_dir` (Section 5.1):

- If `cwd` is omitted, `resolved_cwd` MUST be the project root.
- If `cwd` is an absolute path, `resolved_cwd` MUST be that path.
- If `cwd` is a relative path, `resolved_cwd` MUST be the project root joined with `cwd`.
- If `resolved_cwd` does not exist, is not a directory, or cannot be entered as a working directory, the adapter MUST fail with exit code `2` before provider invocation.

### 5.1 Output File I/O Semantics (MVP)

These rules apply when `request_delivery=output_file` and/or `response_mode=output_file_json`.

- The adapter MUST resolve `io_dir`:
  - If `io_dir` is omitted, it MUST default to `.parley/provider-io`.
  - If `io_dir` is a relative path, it MUST be resolved relative to the resolved `cwd`.
  - If the resolved `io_dir` exists and is not a directory, the adapter MUST treat this as a usage/configuration failure with exit code `2` before provider invocation.
  - If the resolved `io_dir` does not exist, the adapter MUST create it (including any missing parent directories) before provider invocation.
  - If the resolved `io_dir` cannot be created or is not writable, the adapter MUST treat this as a parser/I/O failure with exit code `3` before provider invocation.

- The adapter MUST derive deterministic per-invocation paths under `io_dir` using `request_id`:
  - `request_path = <io_dir>/<request_id>.request.json`
  - `response_path = <io_dir>/<request_id>.response.json`

- The adapter MUST enforce that `request_id` is path-safe under the rules in Section 6.1. If `request_id` violates those rules, the adapter MUST treat this as invalid usage/configuration and fail with exit code `2` before provider invocation.

- The adapter MUST set environment variables for the provider process:
  - `PARLEY_REQUEST_PATH=<absolute request_path>`
  - `PARLEY_RESPONSE_PATH=<absolute response_path>`

- When `request_delivery=output_file`:
  - The adapter MUST serialize the request JSON object (Section 6) as UTF-8 JSON and write it to `PARLEY_REQUEST_PATH` before process invocation.
  - If the request file cannot be created or written, the adapter MUST fail before invocation with exit code `3`.

- When `response_mode=output_file_json`:
  - The adapter MUST treat `PARLEY_RESPONSE_PATH` as the sole response content source.
  - After process completion, the adapter MUST apply the failure precedence rules in Section 9.1.
  - If the process exit code is `0` (success), the adapter MUST read `PARLEY_RESPONSE_PATH` and parse it as the response JSON object (Section 7).
  - If the response file is missing, unreadable, not a JSON object, or schema-invalid, the adapter MUST classify this as `provider_invalid_output`.
  - If stdout contains JSON but the response file is missing/invalid, the adapter MUST still classify the invocation as `provider_invalid_output`.

- Transport files:
  - Request/response files under `io_dir` are transient transport files and MUST NOT be treated as Parley artifacts, report evidence, or durable audit logs.

- Cleanup:
  - After the adapter has read and parsed the needed files, it MUST attempt to delete the request/response files it created before reporting completion.
  - Cleanup failures MUST NOT change the provider classification outcome.

### 5.2 StdIO and Arg I/O Semantics (MVP)

These rules apply when `request_delivery` is `stdin_json`, `stdin_prompt`, or `argument_prompt`, and/or when `response_mode` is `stdout_json` or `stdout_json_envelope`.

Deterministic process invocation (MVP):

- The adapter MUST execute provider commands as an explicit argv list (no shell interpolation).
- The adapter MUST decode stdout/stderr as UTF-8 for parsing and telemetry. Invalid UTF-8 sequences MUST be treated as provider invalid output when stdout is used as the response source and the process exit code is `0`.

Command resolution (MVP):

- If `command` is an absolute path, the adapter MUST invoke that path as given.
- If `command` is not an absolute path, the adapter MUST invoke the provider by passing `command` as argv[0] and relying on the host platform's normal executable search using the provider process environment `PATH`.
- If provider process launch fails because `command` cannot be found or cannot be executed, the adapter MUST classify the attempt as `provider_unavailable`.

Request payload canonicalization (MVP):

- When the adapter serializes a request JSON object for delivery as text (stdin or argv), it MUST:
  - serialize as UTF-8 JSON with no BOM,
  - use a stable serialization (stable key ordering; no non-deterministic whitespace),
  - append exactly one trailing `\n` when writing to stdin.

Request delivery modes (MVP):

- When `request_delivery=stdin_json`:
  - The adapter MUST write the canonicalized request JSON text to stdin.
  - The adapter MUST close stdin immediately after writing the payload.

- When `request_delivery=stdin_prompt`:
  - The adapter MUST write a single UTF-8 text prompt to stdin and then close stdin.
  - The prompt MUST include the request JSON object (Section 6) verbatim as an embedded JSON block.
  - The prompt MUST instruct the provider to return exactly one JSON object response matching Section 7.
  - The prompt text outside the embedded JSON is not semantically authoritative for translation quality; its purpose is deterministic transport for CLIs that only accept prompt text via stdin.

- When `request_delivery=argument_prompt`:
  - The adapter MUST construct argv as: `[command] + args + [payload_arg]`.
  - `payload_arg` MUST be the canonicalized request JSON text (Section 6), without the trailing `\n`.
  - The adapter MUST NOT quote, escape, or shell-interpolate `payload_arg` beyond the host platform's normal argv passing.

Response source and parsing (MVP):

- After process completion, the adapter MUST apply the failure precedence rules in Section 9.1.

- When `response_mode=stdout_json`:
  - The adapter MUST treat stdout as the sole response content source.
  - The adapter MUST ignore stderr for JSON extraction/parsing.
  - If the process exit code is `0` (success), the adapter MUST parse stdout into exactly one JSON object (Section 7).

- When `response_mode=stdout_json_envelope`:
  - The adapter MUST treat stdout as the sole response content source.
  - The adapter MUST ignore stderr for JSON extraction/parsing.
  - If the process exit code is `0` (success), the adapter MUST parse stdout into exactly one JSON object.
  - The adapter MUST then unwrap the response object according to Section 8.1 before schema validation.

Provider commands MUST be executed as an explicit argv list, not through shell interpolation. If a future adapter requires shell behavior, it MUST treat that as provider-specific trusted configuration and MUST NOT interpolate localization content or provider request fields into shell source text.

If the provider process exceeds `timeout_seconds`, Parley MUST terminate the provider process and any child process group it started when the host platform supports that behavior.

Parley MUST NOT stream provider stdout directly to the user as authoritative output. Provider stdout is process evidence until it has been parsed and schema-validated.

Parley MUST NOT include local absolute paths, credentials, API keys, or raw secrets in the provider request unless a future explicitly approved integration requires them. Normal MVP provider requests SHOULD identify files by project-root-relative logical paths when file identity is needed.

## 6. Translation Request Envelope

For provider-backed translation, Parley MUST send a single JSON object request with:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Must be `"1.0"`. |
| `request_id` | string | yes | Deterministic per provider invocation attempt (Section 6.1). |
| `operation` | string | yes | Must be `translate_batch` for MVP translation. |
| `provider_id` | string | yes | Requested provider adapter ID. |
| `source_locale` | string | no | Optional batch-level source locale. If present, it MUST equal every entry `source_locale` value. |
| `target_locale` | string | no | Optional batch-level target locale. If present, it MUST equal every entry `target_locale` value. |
| `project_context` | object | no | Optional batch-level project context. If present, it MUST be deep-equal to every entry `project_context` value. |
| `entries` | array | yes | Entries requiring provider generation, in canonical-key order. |

Each request entry MUST include:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | string | yes | Canonical localization key. |
| `source_locale` | string | yes | Source locale for this entry. |
| `target_locale` | string | yes | Target locale for this entry. |
| `source_text` | string | yes | Authoritative source text. |
| `protected_text` | string | yes | Source text after Parley placeholder/sentinel protection. |
| `context_description` | string or null | yes | Per-key context when available. |
| `project_context` | object | yes | Minimal context needed for translation. May be empty only if the translation workflow permits provider generation for that entry. |
| `glossary_constraints` | array | yes | Applicable glossary constraints, possibly empty. |
| `placeholder_tokens` | array | yes | Placeholder/token summary from the placeholder integrity layer. |
| `translation_memory_candidates` | array | yes | Candidate summary supplied as provider context, possibly empty. |

### 6.1 Request ID Rules (MVP)

`request_id` is the deterministic identifier for a single provider invocation attempt. It is used for response matching (Section 7) and for file-based transport identity (Section 5.1).

Requirements (MVP):

- `request_id` MUST be deterministic for the same canonical ID input record defined below.
- `request_id` MUST be unique per provider invocation attempt within a single Parley run.
- `request_id` MUST be path-safe:
  - MUST match the regex: `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`
  - MUST NOT contain path separators, whitespace, or control characters.

Derivation rule (MVP):

- Parley MUST treat retries as separate provider invocation attempts, each with its own `request_id`.
- Parley MUST assign `invocation_ordinal` as a stable, monotonic counter for each distinct provider request constructed within a single Parley run:
  - A "distinct provider request" is the Section 6 request object Parley constructs for the provider call (excluding the per-attempt `attempt_ordinal`).
  - Starts at `1` for the first distinct provider request constructed in the run.
  - Increments by `1` for each subsequent distinct provider request constructed in that run.
  - A retry of the same provider request MUST retain the original `invocation_ordinal` and MUST NOT consume the next `invocation_ordinal`.
- Parley MUST assign `attempt_ordinal` as a stable, monotonic counter for retries of the same provider request:
  - Starts at `1` for the first invocation attempt for that `invocation_ordinal`.
  - Increments by `1` for each retry attempt of that same provider request.
  - For a new non-retry provider request (a new `invocation_ordinal`), `attempt_ordinal` MUST start at `1`.
- Parley MUST derive `request_id` from a canonical ID input record with exactly these keys:
  - `provider_id`
  - `operation`
  - `source_locale`
  - `target_locale`
  - `entry_keys` (array of strings; exactly the ordered request entry keys)
  - `invocation_ordinal` (integer; stable per distinct provider request within the run)
  - `attempt_ordinal` (integer; starts at `1` for the first attempt, increments by 1 per retry)

Locale derivation (MVP):

- For the canonical ID input record fields `source_locale` and `target_locale`:
  - If the batch-level `source_locale` / `target_locale` fields are present on the request, Parley MUST use those (after normalization).
  - Otherwise, Parley MUST derive them from the per-entry `source_locale` / `target_locale` values (after normalization).
- For MVP `translate_batch` provider calls, mixed per-entry locales are invalid. If entry locales are not identical across all entries, the adapter MUST fail with exit code `2` before provider invocation.

Canonicalization (MVP):

- The canonical ID input record MUST be serialized as stable JSON (stable key ordering; no non-deterministic whitespace).
- Strings in the ID input record MUST be normalized by: (1) Unicode NFC, (2) convert CRLF and CR to LF, (3) trim leading/trailing whitespace.

Construction (MVP):

- Parley MUST compute `request_id` as: `<provider_id>-<hex_sha256>-a<attempt_ordinal>` where:
  - `<hex_sha256>` is the lowercase hex SHA-256 digest of the canonical ID input record bytes.
  - The adapter MUST truncate `<hex_sha256>` deterministically to ensure the final `request_id` satisfies the path-safe constraints above, using this rule:
    - Let `suffix = "-a<attempt_ordinal>"` and `prefix = "<provider_id>-"`.
    - Let `max_digest_len = 64 - len(prefix) - len(suffix)`.
    - The adapter MUST use `digest_len = min(32, max_digest_len)` and set `<hex_sha256>` to the first `digest_len` hex characters.
    - If `max_digest_len < 8`, the adapter MUST treat the provider configuration as invalid and fail with exit code `2` before provider invocation (because no conforming `request_id` can be constructed under the MVP path-safe constraints).
  - The final `request_id` MUST be validated against the path-safe constraints above before invocation.

Notes:

- `request_id` is not a security boundary.
- If an implementation chooses to delegate `request_id` creation to another layer, the adapter MUST still validate that the provided `request_id` meets the requirements and MUST reject invalid IDs before invocation (exit code `2`).

Request validation rules (MVP):

- Provider requests MUST contain only entries that reached the translation workflow's `generated` path. Keys that were skipped, reused, or failed before provider generation MUST NOT be sent to the provider CLI.
- For MVP `translate_batch` provider calls, all request entries MUST have identical `source_locale` and identical `target_locale` values. If they do not, the adapter MUST fail with exit code `2` before provider invocation.
- If batch-level `source_locale`, `target_locale`, or `project_context` are present and do not match the corresponding per-entry values, the adapter MUST treat this as invalid configuration/usage and fail with exit code `2` before provider invocation.

## 7. Translation Response Envelope

A provider CLI response MUST resolve to a JSON object with:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Must be `"1.0"`. |
| `request_id` | string | yes | Must match the request. |
| `provider_id` | string | yes | Provider adapter ID that produced the response. |
| `status` | string | yes | One of `ok`, `partial`, or `failed`. |
| `entries` | array | yes | Per-entry responses. |
| `provider_metadata` | object or null | yes | Optional provider metadata. |

Each response entry MUST include:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | string | yes | Canonical key from the request. |
| `status` | string | yes | One of `translated`, `refused`, or `failed`. |
| `translated_text` | string or null | yes | Required and non-null only when `status=translated`. |
| `failure_reason` | string or null | yes | Required and non-null when `status` is `refused` or `failed`. |

The response MUST NOT include entries for keys that were not present in the request. If it does, Parley MUST treat the provider output as invalid.

The response `provider_id` MUST equal the request `provider_id` after the same string normalization rules as Section 6.1. If it does not, the adapter MUST treat the provider output as invalid and classify the invocation as `provider_invalid_output`.

The response MUST include exactly one entry for every request entry. Missing response entries, duplicate keys, non-string translated text, malformed JSON, non-object JSON, or schema-invalid output MUST be treated as provider invalid output.

### 7.1 Aggregate Status Invariants (MVP)

The aggregate response `status` MUST be consistent with per-entry statuses as follows:

- `status=ok` is legal only when every entry has `status=translated`.
- `status=partial` is legal only when:
  - at least one entry has `status=translated`, and
  - at least one entry has `status=refused` or `status=failed`.
- `status=failed` is legal only when every entry has `status=refused` or `status=failed`.

If the aggregate `status` violates these invariants, the adapter MUST treat the provider output as invalid and classify the invocation as `provider_invalid_output`.

## 8. Provider Output Parsing

Provider-specific adapters MAY unwrap known CLI envelopes only when `response_mode=stdout_json_envelope`, using the unwrapping rules in Section 8.1.

For `response_mode=stdout_json` and `response_mode=output_file_json`, the parsed JSON object MUST already be the Section 7 response object; adapters MUST NOT apply envelope unwrapping for those modes.

After provider-specific envelope unwrapping (when permitted), the adapter MUST validate the normalized response object against the Parley provider response schema before the translation workflow consumes it.

The MVP does not require provider-output formatting tolerance transforms (for example, Markdown-fenced JSON extraction). Adapters MUST NOT attempt heuristic repair that changes provider-provided field values.

### 8.1 `stdout_json_envelope` Unwrapping Rules (MVP)

When `response_mode=stdout_json_envelope`, the adapter MUST:

- Parse stdout into exactly one JSON object `envelope`.
- Derive the candidate response object as follows:
  - If `envelope` contains a top-level key `parley_response`, use `envelope.parley_response`.
  - Else if `envelope` contains `structured_output`, use `envelope.structured_output`.
  - Else if `envelope` contains `result`, use `envelope.result`.
  - Else if `envelope` contains `response`, use `envelope.response`.
  - Else treat the entire `envelope` as the candidate response object.
- Require the derived candidate to be a JSON object. Otherwise classify as `provider_invalid_output`.
- Validate the derived candidate against the Section 7 response schema.

## 9. Failure Classification

Provider invocation failures map to Parley translation behavior as follows:

| Condition | Provider classification | CLI exit interaction |
| --- | --- | --- |
| Provider executable missing or cannot be launched | `provider_unavailable` | Required provider work exits `4`. |
| Provider times out | `provider_timeout` | Required provider work exits `4`. |
| Provider exits non-zero | `provider_process_failed` | Required provider work exits `4`. |
| Provider stdout/output file missing | `provider_invalid_output` | Required provider work exits `4`. |
| Provider output is not parseable JSON object | `provider_invalid_output` | Required provider work exits `4`. |
| Provider response fails schema validation | `provider_invalid_output` | Required provider work exits `4`. |
| Provider returns refused/failed for one or more requested keys | `provider_failed` | Required provider work exits `4`. |

### 9.1 Failure Signal Precedence (MVP)

When multiple failure signals are present for a single provider invocation attempt, the adapter MUST classify the attempt using the first matching condition in this precedence order:

1. `provider_unavailable`: provider executable missing / cannot be launched (process never started).
2. `provider_timeout`: timeout handling fired.
3. `provider_process_failed`: process started and exited with a non-zero exit code.
4. `provider_invalid_output`: process exit code is `0`, but response source is missing/unreadable, not a JSON object, not valid UTF-8 (when stdout is the response source), or schema-invalid.
5. `provider_failed`: process exit code is `0` and response is schema-valid, but one or more requested entries are `refused` or `failed`.

Consequences (MVP):

- If the process exit code is non-zero, the adapter MUST classify the attempt as `provider_process_failed` regardless of whether stdout/stderr or an output file contains JSON.
- The adapter MUST only parse/validate provider output for `provider_invalid_output` / `provider_failed` classification when the process exit code is `0`.

### 9.2 Mapping to CLI Report Provider Failure Categories (MVP)

When the CLI command writes a report with `provider_status=failed`, it MUST set `provider_failure_category` according to the CLI Command Specification's closed enum (`unavailable`, `invalid_output`, `error`). The adapter classification maps as:

| Adapter provider classification | CLI `provider_failure_category` |
| --- | --- |
| `provider_unavailable` | `unavailable` |
| `provider_invalid_output` | `invalid_output` |
| `provider_timeout` | `error` |
| `provider_process_failed` | `error` |
| `provider_failed` | `error` |

When a required provider operation fails, the translation report behavior is owned by the CLI Command Specification. The report MUST classify affected generated-path keys as failed according to the CLI Command Specification's provider failure rules.

Provider failures MUST NOT be reported as translation-memory misses, parser failures, or placeholder findings unless those independent failures also occurred.

### 9.3 Partial Batch Consumption Alignment (MVP)

When the provider response is schema-valid but contains one or more entries with `status=refused` or `status=failed` (that is, `provider_failed` per Section 9.1), Parley MUST apply one deterministic alignment rule when consuming translated entries from that batch.

Definitions:

- The provider request `entries` array is in canonical-key order (Section 6).
- The response `entries` array includes exactly one entry per requested key (Section 7).
- The *first failed key* is the first key in the request entry order whose corresponding response entry has `status=refused` or `status=failed`.

Consumption rule (MVP):

- For keys that appear *before* the first failed key in request order:
  - If the response entry `status=translated`, its `translated_text` is usable and MAY be consumed.
- For the first failed key, and for any keys that appear *after* it in request order:
  - Parley MUST treat the batch as having reached the provider-failure boundary for the invocation and MUST NOT treat any `translated_text` in those later entries as usable provider output for generated-path consumption.

Clarification (MVP):

- In this section, “consumed” means only that these validated translated values may be surfaced to the translation workflow as candidate generated outputs for per-key outcome computation and translation reporting.
- Durable target write-back and any translation-memory mutation remain governed by the CLI Command Specification’s provider-failure and commit rules; a provider failure (exit code `4`) MUST NOT be interpreted by the adapter as authorization to commit partial provider output to localization artifacts or translation memory.

This rule aligns batch-mode provider responses to the CLI command’s deterministic provider-failure semantics (first failed key is `provider_failed`; later keys that would require provider generation are handled via the CLI’s post-failure rule), while keeping write-back authority in the CLI command surface.

## 10. Telemetry

For each provider invocation attempt (including attempts that are unavailable, timed out, or exited non-zero), Parley MUST capture a provider telemetry object containing:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `provider_id` | string | yes | Provider adapter ID. |
| `request_id` | string | yes | Stable per invocation attempt identifier (Section 6.1). |
| `invocation_ordinal` | integer | yes | Stable per distinct provider request (Section 6.1). |
| `attempt_ordinal` | integer | yes | Stable attempt counter for that `invocation_ordinal` (Section 6.1). |
| `provider_classification` | string or null | yes | Null when the provider response is consumed as successful provider output. Otherwise one of Section 9 provider classifications. |
| `command` | string | yes | Executable invoked. |
| `started_at` | string | yes | UTC RFC 3339 timestamp. |
| `finished_at` | string or null | yes | Null if timed out before clean completion. |
| `duration_ms` | integer or null | yes | Wall-clock duration. |
| `exit_code` | integer or null | yes | Null when unavailable or when timeout handling fires before an exit code is available. |
| `timed_out` | boolean | yes | Whether timeout handling fired. |
| `token_usage` | object or null | yes | Provider token usage when available. |

Telemetry MUST be captured by the adapter layer and returned to the translation workflow / report-writing layer as part of the provider invocation result. These fields are the stable correlation identity between a specific provider attempt and its translation/report outcome classification.

The CLI Command Specification owns whether and how this telemetry is persisted into a report artifact.

Telemetry MAY include redacted stdout/stderr excerpts for debugging in developer/test contexts, but normal MVP reports MUST NOT require full raw provider prompts or full raw provider stdout/stderr.

## 11. Retry Policy

The Translation Workflow Specification owns whether retries are attempted and which conditions are retryable.

This protocol defines one provider invocation attempt. If retries are implemented:

- Each attempt MUST be independently timed, parsed, validated, classified, and have telemetry captured.
- Each attempt MUST have its own `request_id` derived by incrementing `attempt_ordinal` as defined in Section 6.1.
- For retries of the same provider request, the attempt MUST retain the original `invocation_ordinal` and increment only `attempt_ordinal`.
- File-based request/response artifacts for different attempts MUST NOT collide.

The final translation report MAY summarize attempts, but MVP report correctness MUST NOT depend on exhaustive retry history.

## 12. Fake CLI Provider Tests

MVP implementation MUST include fake CLI tests that exercise the adapter protocol without calling real LLM tools.

At minimum, tests MUST cover:

- Successful schema-valid provider response.
- Non-zero provider process exit.
- Timeout handling.
- Non-JSON stdout.
- JSON that is not an object.
- Schema-invalid response.
- Missing response entry for a requested key.
- Duplicate response entry for a requested key.
- Provider refusal/failure for a requested key.

Transport and parser mode coverage (MVP):

- Tests MUST cover `request_delivery=output_file` request-path creation and the invariant that the request JSON is written to `PARLEY_REQUEST_PATH` before invocation.
- Tests MUST cover `response_mode=output_file_json` response-path handling, including missing/unreadable/invalid response-file classification as `provider_invalid_output` even if stdout contains JSON.
- Tests MUST cover `response_mode=stdout_json_envelope` unwrapping, including the top-level key precedence order in Section 8.1 and schema validation of the derived candidate object.
- Tests MUST assert canonical request delivery semantics for at least one stdin/argv delivery mode (`stdin_json` or `argument_prompt`), including the trailing-newline rule for stdin and the no-trailing-newline rule for argv.

Mixed-signal precedence (MVP):

- Tests MUST cover the precedence rule that a non-zero exit code classifies as `provider_process_failed` even if a schema-valid response is present on stdout or at `PARLEY_RESPONSE_PATH`.

Telemetry acceptance (MVP):

- Tests MUST assert that telemetry is captured for at least one successful attempt and at least one failed attempt, and that required telemetry fields are present.

Tests SHOULD assert that provider failures do not mutate target localization files and that translation reports use the provider failure categories required by the CLI Command Specification.

## 13. MVP Deferrals

The MVP does not require:

- Dynamic provider plugin loading.
- Streaming provider responses.
- Multi-turn provider sessions.
- Rich provider-specific diagnostics in user-facing reports.
- Exhaustive provider telemetry schemas.
- Governance-grade audit logs of full prompts and raw responses.
- Durable persistence of provider transport request/response contents as Parley artifacts (including leaving `.parley/provider-io` files as durable evidence).
- Provider-backed confidence review as part of translation unless separately enabled by the owning workflow spec.
- Provider-output formatting tolerance transforms (for example, Markdown-fenced JSON extraction).

Provider CLI adapters should be designed so these capabilities can be added later without changing the translation workflow's core generated/reused/skipped/failed outcome model.
