# Parley MVP Implementation Plan

Updated: 2026-05-17

This plan turns the converged Parley MVP specs into an implementation sequence. It is intentionally broad enough to keep later slices visible, but concrete enough to make the first slice executable.

## Planning Inputs

Authoritative or build-target inputs:

- [HLD / Architecture](hld-architecture.md)
- [CLI Command Spec](specs/01-cli-command-spec.md)
- [Project Artifact Schema Spec](specs/02-project-artifact-schema-spec.md)
- [Validation and Error Taxonomy Spec](specs/07-validation-error-taxonomy-spec.md)
- [Provider CLI Adapter Protocol Spec](specs/09-provider-cli-adapter-protocol-spec.md)

Supporting inputs:

- [Spec Tracking Matrix](SPEC_TRACKING_MATRIX.md)
- [Spec Index](specs/00-spec-index.md), as navigation/dependency context only

Implementation stance:

- Keep Parley project-first for MVP.
- Treat paired-file translation, non-project report roots, diagnostic mode, exhaustive report schemas, retry/resume matrices, and broad production operability as post-MVP unless explicitly promoted.
- Prefer small, deterministic, testable service boundaries over large orchestration flows.
- Let leaf specs own detailed contracts; the HLD owns architecture boundaries.
- Keep the provider CLI command runner generic where practical, but keep Parley translation semantics in the provider/translation layer.

## Slice Roadmap

### Slice 0: Project Skeleton

Goal: establish the package and test shape without committing to every workflow.

Status: implemented as the initial Python package skeleton in `src/parley`, with a stdlib CLI/test setup.

Scope:

- Choose the Python package layout and CLI entrypoint.
- Add test harness and fixture conventions.
- Add deterministic JSON/YAML serialization helpers.
- Add basic path canonicalization and project-root utilities.
- Add shared error/result types matching the MVP exit-code families.
- Add report writer scaffolding without exhaustive report schemas.

Exit criteria:

- `parley --help` runs locally.
- Tests can create an isolated temporary project root.
- Serialization helpers are covered by focused tests.
- No provider, translation, or parser implementation is required yet beyond minimal stubs.

Implemented notes:

- CLI entrypoint is `parley.cli:main` with `python -m parley` support.
- Serialization is currently stdlib-only: deterministic JSON plus a narrow YAML writer for Parley-owned MVP artifacts.
- Parser support is intentionally minimal and exists only to support `project init` canonical inventory generation; Slice 3 should revisit this boundary.

### Slice 1: Project Init

Goal: implement the first useful project workflow: `parley project init`.

Status: implemented at MVP depth with deterministic artifact creation, report writing, `--force`, and focused tests.

Scope:

- Resolve project root:
  - `--project-root` is allowed for init.
  - If omitted, use the current working directory.
- Validate init inputs:
  - `--name NAME` is required.
  - `--authoritative PATH` is required and must resolve under the project root.
  - `--locale LOCALE` is required.
  - `--format FORMAT` may be explicit or inferred only where deterministic.
- Parse the authoritative localization enough to build the initial inventory and canonical inventory.
- Create the MVP artifact set:
  - `parley.yaml`
  - `inventory.yaml`
  - `canonical-inventory.json`
  - `context-anchor.yaml`
  - `glossary.yaml`
  - `translation-memory.sqlite`
  - `reports/`
- Create a schema-valid empty context anchor placeholder without provider calls.
- Create an empty glossary placeholder with `rules: []`.
- Initialize translation memory as an empty SQLite database or minimal placeholder consistent with the Translation Memory spec once its minimum DB contract is confirmed.
- Write an initialization report through the shared report writer.
- Implement `--force` as an atomic replacement path for managed artifacts.

Key acceptance criteria:

- Without `--force`, if any managed init path already exists, init fails with exit code `2` and leaves existing artifacts unchanged.
- With `--force`, validation, parsing, derivation, staging, and report preparation happen before final replacement.
- With `--force`, existing `.parley/` contents and existing reports are preserved.
- A staging or commit failure exits with code `3` and restores pre-invocation managed artifacts and reports.
- The final commit order is deterministic.
- The generated artifacts use `schema_version: "1.0"` where required.
- JSON object keys are serialized deterministically.
- Report paths stay under `<project-root>/reports/` and never silently overwrite an existing report file.
- Tests cover successful init, conflict without `--force`, replacement with `--force`, invalid authoritative path, parse/IO failure, and deterministic artifact output.

Out of scope:

- Provider calls.
- Populating per-key context.
- Full validation matrix.
- Translation memory import/export.
- Translation workflow.

Implemented notes:

- `project init` supports iOS `.strings` and Android XML enough to derive the first canonical inventory.
- `translation-memory.sqlite` is initialized as an empty SQLite database with minimal metadata only; richer table semantics remain Slice 7.
- Initialization reports are written under `reports/validation/` following the CLI spec's current command mapping.
- Rollback coverage is implemented for normal command-return failures during the managed artifact commit path; crash/power-loss recovery remains out of scope per the CLI spec.

### Slice 2: Artifact Loading and Validation

Goal: make Parley able to load and validate its own project artifacts consistently.

Status: initial MVP implementation complete.

Scope:

- Implement artifact readers for `parley.yaml`, `inventory.yaml`, `canonical-inventory.json`, `context-anchor.yaml`, optional `glossary.yaml`, and `translation-memory.sqlite`.
- Implement minimum required-field validation.
- Implement missing/schema-invalid failure categories.
- Add validation report emission for project artifact failures.
- Keep validation depth to required fields, containment, ownership boundaries, and obvious failure categories.

Exit criteria:

- `parley validate` can classify project artifact presence and schema validity.
- Missing or schema-invalid required artifacts produce deterministic exit behavior and reports.
- Optional missing `glossary.yaml` behaves as an empty ruleset.

Implemented notes:

- Added artifact readers/inspectors for the current Parley-owned YAML/JSON/SQLite artifacts.
- Added `parley project inspect` for deterministic artifact health output.
- Added `parley validate` with selected-entry ordering, report/no-report behavior for pre-selection failures, and validation reports after entry selection.
- Validation depth is intentionally minimum-schema plus local structural/placeholder findings.

### Slice 3: Parser Interface

Goal: establish the parser adapter boundary and one concrete parser.

Status: initial reusable parser boundary complete.

Scope:

- Define normalized localization entry shape.
- Implement parser adapter registration/selection.
- Implement stable parser errors.
- Implement placeholder extraction hook.
- Start with one localization format, likely iOS `.strings`, unless implementation inspection suggests Android XML is easier for the first vertical slice.

Exit criteria:

- The init and validation workflows can parse one real localization format.
- Parser output is deterministic.
- Parser failures map to exit code `3` and `parser` or `io` failure categories as appropriate.

Implemented notes:

- The parser module now serves both project initialization and validation/localization workflows.
- Current concrete formats are iOS `.strings` and Android XML.
- Placeholder extraction is deliberately lean and should be expanded when the Placeholder Token Integrity spec is synthesized further.

### Slice 4: Inventory and Canonical Baseline

Goal: make inventory and canonical inventory updates reliable.

Status: initial MVP implementation complete.

Scope:

- Implement `parley localization add` at MVP depth.
- Manage authoritative vs target localization records.
- Regenerate canonical inventory when authoritative coherence applies.
- Preserve canonical entry timestamps according to content-hash change rules.
- Maintain deterministic inventory hash and entry ordering.

Exit criteria:

- Inventory updates are atomic.
- Canonical inventory generation is deterministic.
- Placeholder signatures are stored for later validation.

Implemented notes:

- Added `parley localization add` for target and constrained authoritative updates.
- Target additions update `inventory.yaml`; authoritative additions/updates refresh `parley.yaml` and `canonical-inventory.json`.
- Multi-file updates use a shared staged commit/rollback helper for normal command-return failures.

### Slice 5: Placeholder Integrity

Goal: validate placeholder compatibility between canonical and target localizations.

Status: initial MVP implementation complete.

Scope:

- Compare placeholder signatures.
- Emit deterministic validation findings for missing, extra, or incompatible placeholders.
- Keep severity/category handling aligned with the Validation and Error Taxonomy spec.

Exit criteria:

- `parley validate` detects placeholder mismatches for parsed target files.
- Findings are stable in ID and order.

Implemented notes:

- Validation compares selected parsed entries against `canonical-inventory.json`.
- Findings currently cover missing keys, extra keys, and placeholder-signature mismatches.
- Detailed token semantics and richer finding taxonomy remain intentionally deferred to later Placeholder/Validation spec tightening.

### Slice 6: Context and Confidence

Goal: support context-anchor loading and MVP confidence behavior without overbuilding provider workflows.

Scope:

- Validate context-anchor presence, schema validity, and populated per-key context.
- Implement confidence mode selection rules for `anchor`, `standalone`, and `none`.
- Add provider adapter boundary if needed, but keep provider behavior minimal and replaceable.
- Emit minimal confidence reports.

Exit criteria:

- Missing, invalid, and unpopulated anchors behave deterministically.
- Provider-skipped behavior is explicit when provider access is unavailable or disabled.

### Slice 7: Translation Memory

Goal: provide the persistence layer needed by translation reuse.

Scope:

- Initialize SQLite translation memory.
- Implement lookup by project/source/target/key/content identity.
- Implement current-record selection and conflict behavior.
- Implement deterministic `updated_at` handling for CLI-written records.
- Keep `confidence_json` and `metadata_json` as MVP-safe expansion fields; richer human/model review evidence remains a future table keyed by TM record ID.

Exit criteria:

- Translation workflows can reuse approved/current records.
- Conflict cases are deterministic and reportable.
- JSONL import/export remains deferred unless needed for a later slice.

### Slice 8: Translation Workflow

Goal: implement `parley translate` for project mode.

Status: initial MVP implementation complete with dummy-provider generation, translation-memory reuse/write-back, deterministic per-key outcomes, dry-run support, project-scoped translation reports, and iOS/Android smoke coverage.

Scope:

- Load project artifacts and canonical key order.
- Require populated context anchor.
- Reuse translation memory where eligible.
- Call provider adapter only for keys that require generation.
- Perform atomic target write-back and translation-memory mutation.
- Emit translation report with per-key outcomes.

Exit criteria:

- Every canonical key follows a deterministic path: skipped, TM reuse, provider generation, or failure.
- Partial file replacement failures roll back or restore according to the CLI spec.
- Translation reports are stable and project-scoped.

Implemented notes:

- Current provider support is intentionally limited to the deterministic dummy provider.
- Real LLM provider work now has its own protocol authority in the Provider CLI Adapter Protocol spec.
- Translation memory write-back exists for generated output; richer review/audit expansion remains deferred.

### Slice 9: Provider CLI Adapter

Goal: replace the dummy-only provider path with a generic command-backed JSON adapter that can support Codex/Claude-style CLIs without baking those CLIs into translation workflow logic.

Status: initial core implemented for `stdin_json` request delivery and `stdout_json` response parsing with fake CLI tests. The provider CLI adapter protocol has reached Whetstone MVP convergence and has been applied back to the source spec.

Scope:

- Add a generic `CommandJsonAdapter` with no Parley translation semantics.
- Support `stdin_json` request delivery first.
- Support `stdout_json` response mode first.
- Execute provider commands as explicit argv lists, with no shell interpolation.
- Resolve working directory deterministically.
- Enforce positive `timeout_seconds`.
- Capture stdout, stderr, exit code, duration, timeout flag, and basic token/usage metadata when available.
- Parse exactly one JSON object from the configured response source.
- Classify process launch failure, timeout, non-zero exit, non-JSON output, non-object JSON, and schema/shape-invalid output.
- Add fake CLI tests covering success and the required failure paths.
- Add a Parley translation-provider wrapper that maps validated adapter responses into the existing translation workflow.

Exit criteria:

- A fake CLI provider can generate translations through `parley translate`.
- Adapter failures do not mutate target localization files.
- Translation reports expose the correct provider status/failure category for required provider work.
- The adapter returns generic invocation results that could be reused by another Parley provider workflow later.
- Existing dummy-provider smoke tests still pass.

Out of scope for the first provider adapter slice:

- `output_file_json` transport.
- `stdin_prompt` and `argument_prompt` transports.
- Hosted API adapters.
- Streaming responses.
- Interactive auth.
- Retry/backoff implementation beyond preserving the protocol boundary.
- Full raw prompt/response diagnostic logging.

### Slice 10: Provider CLI Transport Expansion

Goal: add the transport modes needed by real-world LLM CLIs after the core command adapter is stable.

Scope:

- Add `output_file_json` request/response transport.
- Add deterministic `io_dir` handling and cleanup behavior.
- Add known-envelope unwrapping for CLIs that return `structured_output` or JSON strings in `result`.
- Add Codex/Claude-oriented adapter configuration helpers if the generic adapter proves sufficient.

Exit criteria:

- Fake CLI tests cover file transport and envelope unwrapping.
- A local configured CLI can be smoke-tested without production strings.
- Provider-specific wrappers stay thin.

### Slice 11: Integration and Hardening

Goal: make the MVP coherent enough to use end to end.

Scope:

- End-to-end fixtures for init, add, validate, and translate.
- CLI help polish.
- Documentation pass against implemented behavior.
- Decide whether non-converged leaf specs need bounded synthesis before expanding scope.

Exit criteria:

- A small sample project can be initialized, validated, and translated through the MVP path.
- Known deferred surfaces remain clearly deferred.

## First Implementation Slice: Immediate Task List

1. Add `src/parley/command_json.py` with a generic result/failure/telemetry model.
2. Implement explicit-argv subprocess execution with cwd resolution and timeout handling.
3. Implement `stdin_json` request delivery and `stdout_json` response parsing.
4. Add a validation hook that can enforce the provider response shape without coupling the adapter to translation semantics.
5. Add fake CLI fixtures/tests for success, non-zero exit, timeout, non-JSON stdout, non-object JSON, missing entries, duplicate entries, and provider refusal/failure.
6. Add a Parley provider wrapper that converts translation requests to adapter request JSON and validated adapter responses back to translation results.
7. Wire one non-dummy provider ID behind a test-only fake command path before attempting Codex/Claude CLI configuration.
8. Run the existing smoke tests plus the new provider adapter tests.
9. Update this plan with implementation discoveries before adding `output_file_json`.

## Deferred Until Explicitly Promoted

- Non-project paired-file translation.
- Non-project report roots.
- Diagnostic mode.
- Exhaustive report schemas.
- Full validation matrices.
- Retry/resume matrices.
- Governance-grade convergence proof.
- Translation memory JSONL import/export.
- Provider CLI `output_file_json`, `stdin_prompt`, and `argument_prompt` transports until the core adapter works.
- Real production provider configuration until fake CLI adapter coverage is solid.
