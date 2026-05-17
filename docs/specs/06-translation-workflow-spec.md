# Translation Workflow Specification

## 1. Scope

This specification defines project-mode and paired-file translation workflows, prompt construction, provider interface, translation memory lookup order, incremental skip rules, glossary injection, retry behavior, and post-generation validation.

It depends on:

- [CLI Command Specification](01-cli-command-spec.md)
- [Project Artifact Schema Specification](02-project-artifact-schema-spec.md)
- [Placeholder and Token Integrity Specification](04-placeholder-token-integrity-spec.md)
- [Confidence Model Specification](05-confidence-model-spec.md)
- [Translation Memory Specification](08-translation-memory-spec.md)
- [Provider CLI Adapter Protocol Specification](09-provider-cli-adapter-protocol-spec.md)

## 2. Provider Interface

```python
class TranslationProvider(Protocol):
    provider_id: str

    def translate_batch(self, request: TranslationBatchRequest) -> TranslationBatchResponse: ...
    def assess_confidence(self, request: ConfidenceRequest) -> ConfidenceResponse: ...
    def compare_semantics(self, request: SemanticComparisonRequest) -> SemanticComparisonResponse: ...
```

Provider responses MUST be validated before use. Invalid provider output after retries is exit code `4`.

Command-line provider adapters are governed by the Provider CLI Adapter Protocol Specification. This workflow spec owns which entries need provider generation and how validated provider results are consumed; the provider CLI protocol owns process invocation, request/response envelopes, schema validation, telemetry, and provider process failure classification.

## 3. Translation Request Entry

Each provider translation entry MUST include:

- `key`
- `source_locale`
- `target_locale`
- `source_text`
- `protected_text`
- `context_description`
- `project_context`
- `glossary_constraints`
- `placeholder_tokens`
- `translation_memory_candidates`

`protected_text` is source text after protected placeholders are replaced by Parley sentinels.

## 4. Prompt Construction Requirements

Prompts MUST instruct providers to:

- Preserve all Parley sentinel tokens exactly.
- Follow glossary constraints.
- Translate for the target locale, not just the language.
- Respect per-string context descriptions.
- Return structured output keyed by localization key.
- Include notes only in metadata fields, not in translated text.

Prompts MUST NOT include API keys or local absolute paths.

## 5. Project-Mode Translation

Project-mode translation requires:

- Valid `parley.yaml`.
- Valid `inventory.yaml`.
- Valid `canonical-inventory.json`.
- Existing `context-anchor.yaml` with project context and per-key context for entries being generated.
- Authoritative localization file.

Missing context anchor is a usage/configuration error with exit code `2`.

## 6. Translation Memory Lookup Order

For each entry, lookup candidates in this order:

1. Exact approved or locked match by `source_content_hash`, target locale, and placeholder signature.
2. Exact reviewed match by `source_content_hash`, target locale, and placeholder signature.
3. Exact machine-generated match by `source_content_hash`, target locale, and placeholder signature.
4. Same key and target locale with compatible placeholder signature.
5. Fuzzy source text match with compatible context and placeholder signature.

Reuse rules:

- Candidate score MUST be at least `0.88`.
- Human-approved or locked candidates SHOULD be reused when source hash and placeholder signature match.
- Locked target entries MUST be skipped unless `--include-locked` is supplied.
- Human-approved target entries MUST be skipped unless `--include-approved` is supplied.

## 7. Incremental Skip Rules

In incremental mode, skip translation when all applicable conditions are true:

- Authoritative `content_hash` has not changed.
- Target entry exists.
- Target entry validation has no `blocking` findings.
- Target aggregate confidence is at least `0.90`, or target status is `approved` or `locked`.
- Glossary version affecting the entry has not changed.
- Placeholder signature has not changed.

Entries MUST be regenerated or revalidated when:

- Key is new.
- Authoritative value changed.
- Placeholder signature changed.
- Translation is missing.
- Existing translation has blocking findings.
- Glossary rules affecting the entry changed.
- Context anchor entry changed materially.

## 8. Glossary Injection

Before provider calls, the glossary engine MUST resolve applicable rules by:

- Source term.
- Source locale.
- Target locale or wildcard.
- Rule type.

Provider prompts MUST include applicable:

- Preferred translations.
- Prohibited translations.
- Protected phrases.
- Untranslated product names.
- Canonical terminology.

Post-generation validation MUST emit `terminology` findings for violations.

## 9. Placeholder Protection and Restoration

The workflow MUST:

1. Extract placeholders from authoritative source.
2. Replace protected tokens with sentinels.
3. Send protected text to provider.
4. Restore sentinels in provider output.
5. Validate placeholder integrity against authoritative entry.

Any unresolved sentinel or altered protected token MUST be a `placeholder_integrity` finding with severity `blocking`.

## 10. Retry Behavior

Provider operations SHOULD retry transient failures up to 3 attempts.

Retryable conditions:

- Timeout.
- Rate limit.
- Transient network error.
- Provider 5xx response.
- Structured output parse failure, if prompt repair is possible.

Non-retryable conditions:

- Authentication failure.
- Unsupported provider/model.
- Content policy refusal that cannot be resolved by reducing context.
- Invalid request generated by Parley.

Failure after retries is exit code `4`.

## 11. Post-Generation Validation

After translation or reuse, Parley MUST run:

- Placeholder validation.
- Structural validation.
- Glossary validation.
- Parser write-back validation.

Parley SHOULD run provider-backed grammar, clarity, and semantic validation when provider access is enabled.

Translation output MUST NOT be written if any generated entry has a `blocking` placeholder finding.

## 12. Translation Report Entries

Each translated or skipped entry SHOULD include:

- `key`
- `source_locale`
- `target_locale`
- `action`: `generated`, `reused`, `skipped`, `blocked`, or `failed`
- `reason`
- `source_content_hash`
- `target_content_hash`
- `memory_id` when reused
- `confidence`
- `findings`

## 13. Paired-File Mode

Paired-file translation:

- Does not require a project.
- Does not use context anchor.
- MAY use glossary or translation memory if explicitly supplied through `--project-root`.
- MUST still run placeholder and structural validation.

Paired semantic comparison MUST be based strictly on the two files being compared.
