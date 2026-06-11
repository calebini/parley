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

## 6. Lint Target Quality

Use lint when the files are structurally valid but you want a release-polish audit before sharing them with reviewers or shipping them.

```sh
PYTHONPATH=src python3 -m parley lint audit \
  --project-root "/path/to/App/parley"
```

The default `basic` profile focuses on high-confidence issues:

- parseability
- missing or extra keys
- placeholder drift
- mojibake or replacement-character encoding artifacts

The default scope is `files`, which is the right pre-share check for localization files. Use `--scope all` to include translation memory records, or `--scope tm` to inspect TM only.

For noisier translation-quality hints, use:

```sh
PYTHONPATH=src python3 -m parley lint audit \
  --project-root "/path/to/App/parley" \
  --profile release
```

The `release` profile also warns about source-equals-target strings and newline-count changes.

For mechanical repairs, dry-run first:

```sh
PYTHONPATH=src python3 -m parley lint fix \
  --project-root "/path/to/App/parley" \
  --dry-run
```

Then apply:

```sh
PYTHONPATH=src python3 -m parley lint fix \
  --project-root "/path/to/App/parley"
```

`lint fix` is intentionally conservative. It applies only high-confidence encoding fixes such as `BiztonsÃ¡gi kÃ³d` to `Biztonsági kód` or mangled smart quotes to proper Unicode quotes. It updates affected target files and matching current TM records, then re-audits before writing the report.

## 7. Prepare Context

`project init` creates blank context slots. Context-aware translation requires those entries to be populated.

Check readiness:

```sh
PYTHONPATH=src python3 -m parley context validate \
  --project-root "/path/to/App/parley"
```

Populate `context-anchor.yaml` manually with concise per-key descriptions. If context is not appropriate for the run, use `--no-context`; Parley will record `context_mode: disabled` in the translation report.

## 8. Prepare A Glossary

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

## 9. Translate One Target

Dry-run first:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/App/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/App/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target
```

`--write-order authoritative` writes target entries in authoritative source-file key order. It preserves entry order only; comments and formatting are normalized by parser adapters.

`--target-conflict-mode preserve_target` is useful for established production target files. When an approved or locked TM entry differs from an existing target-file value, Parley preserves the target-file value and reports the key as `target_preserved` instead of failing. Missing target keys can still be filled from TM or a provider.

## 10. Translate All Targets

Dry-run all registered targets:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target
```

Restrict a batch:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-locale de-DE \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Batch translation writes one per-target translation report plus one `translate_batch` roll-up report.

## 11. Reuse Modes

- `tm_only`: never call a provider. Missing TM candidates become failed outcomes.
- `tm_then_provider`: reuse TM where possible, call provider for the remaining keys.
- `provider_only`: skip TM reuse and generate anything that is not already skipped.

For existing production corpora, `tm_then_provider` is usually the right mode.

For production corpora where the checked-in target files are the source of truth, combine `tm_then_provider` with `--target-conflict-mode preserve_target`.

## 12. Reports

Reports are written under:

- `reports/validation/`
- `reports/lint/`
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
