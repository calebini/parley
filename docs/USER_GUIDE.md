# Parley User Guide

This guide covers day-to-day Parley usage for project-mode localization work.

## 1. Create A Project

Choose an authoritative source localization. For iOS this is usually `en.lproj/Localizable.strings`; for Android it is usually `values/strings.xml`.

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "/path/to/App/parley" \
  --name "My App" \
  --authoritative "/path/to/App/en.lproj/Localizable.strings" \
  --locale en-US
```

`project init` creates:

- `parley.yaml`
- `inventory.yaml`
- `canonical-inventory.json`
- `context-anchor.yaml`
- `glossary.yaml`
- `translation-memory.sqlite`
- `reports/`

If `--project-root` is a folder inside the app directory, Parley keeps its artifacts separate while still referencing localization files through `project.localization_root`.

## 2. Inspect The Project

```sh
PYTHONPATH=src python3 -m parley project inspect \
  --project-root "/path/to/App/parley"

PYTHONPATH=src python3 -m parley localization list \
  --project-root "/path/to/App/parley"
```

Use locale lookup when you are unsure which locale code to register:

```sh
PYTHONPATH=src python3 -m parley locale list --query german
```

## 3. Register Target Files

Register one target:

```sh
PYTHONPATH=src python3 -m parley localization add \
  "/path/to/App/fr.lproj/Localizable.strings" \
  --project-root "/path/to/App/parley" \
  --locale fr-FR
```

An incomplete target can exit with validation findings. That is expected when the file is missing keys; the registration can still be useful for later translation.

## 4. Import Existing Translations Into TM

For one already-registered target:

```sh
PYTHONPATH=src python3 -m parley tm import-target \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --status approved
```

For a production iOS corpus:

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/App/parley" \
  --source-root "/path/to/App" \
  --status approved \
  --dry-run
```

Review the report and then apply:

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/App/parley" \
  --source-root "/path/to/App" \
  --status approved
```

Use repeated locale overrides when folder names need clarification:

```sh
--locale-map bg=bg-BG --locale-map hr=hr-HR
```

TM import never rewrites production localization files. It imports only keys that exist in the target and have matching placeholder signatures.

## 5. Validate Targets

```sh
PYTHONPATH=src python3 -m parley validate \
  --project-root "/path/to/App/parley" \
  --no-authoritative
```

Validation reports:

- missing keys
- extra keys
- placeholder mismatches
- parser errors
- IO errors
- glossary terminology findings

An imported partial corpus usually validates with `missing_key` findings. That is a useful baseline, not necessarily a bad project state.

## 6. Prepare Context

`project init` creates blank context slots. Context-aware translation requires those entries to be populated.

Check readiness:

```sh
PYTHONPATH=src python3 -m parley context validate \
  --project-root "/path/to/App/parley"
```

Populate `context-anchor.yaml` manually with concise per-key descriptions. If context is not appropriate for the run, use `--no-context`; Parley will record `context_mode: disabled` in the translation report.

## 7. Prepare A Glossary

Create or refresh a glossary skeleton:

```sh
PYTHONPATH=src python3 -m parley glossary init \
  --project-root "/path/to/App/parley" \
  --with-example
```

Validate glossary syntax:

```sh
PYTHONPATH=src python3 -m parley glossary validate \
  --project-root "/path/to/App/parley"
```

List terms:

```sh
PYTHONPATH=src python3 -m parley glossary list \
  --project-root "/path/to/App/parley"
```

Suggest draft terms from TM:

```sh
PYTHONPATH=src python3 -m parley glossary suggest \
  --project-root "/path/to/App/parley" \
  --from-tm \
  --target-locale fr-FR
```

Suggestions do not affect translation until promoted into `glossary.yaml`.

## 8. Translate One Target

Dry-run first:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/App/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/App/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative
```

`--write-order authoritative` writes target entries in authoritative source-file key order. It preserves entry order only; comments and formatting are normalized by parser adapters.

## 9. Translate All Targets

Dry-run all registered targets:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative
```

Restrict a batch:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-locale de-DE \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --dry-run
```

Batch translation writes one per-target translation report plus one `translate_batch` roll-up report.

## 10. Reuse Modes

- `tm_only`: never call a provider. Missing TM candidates become failed outcomes.
- `tm_then_provider`: reuse TM where possible, call provider for the remaining keys.
- `provider_only`: skip TM reuse and generate anything that is not already skipped.

For existing production corpora, `tm_then_provider` is usually the right mode.

## 11. Reports

Reports are written under:

- `reports/validation/`
- `reports/translation/`
- `reports/translation_memory/`
- `reports/glossary/`

Use reports to answer:

- Which keys were missing?
- Which translations were reused from TM?
- Which keys were generated?
- Did the target file change?
- Did TM change?
- Was provider work attempted?
- Did a run only dry-run?

## 12. Common Exit Codes

- `0`: success.
- `1`: completed with validation/per-key findings.
- `2`: usage or project artifact problem.
- `3`: IO, parser, or report/write failure.
- `4`: required provider operation failed.

For corpus import and validation, exit `1` can be a normal partial-corpus state when the only findings are missing keys.
