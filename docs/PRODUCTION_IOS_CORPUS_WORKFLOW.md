# Production iOS Corpus Workflow

This workflow is for an existing iOS localization corpus with sibling `.lproj` folders, for example:

```text
MyApp/
  en.lproj/Localizable.strings
  fr.lproj/Localizable.strings
  de.lproj/Localizable.strings
  ...
```

The goal is to seed Parley from existing production translations, then translate only missing or new strings.

## 1. Initialize A Project Beside The Corpus

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "/path/to/MyApp/parley" \
  --name "MyApp" \
  --authoritative "/path/to/MyApp/en.lproj/Localizable.strings" \
  --locale en-US
```

This creates Parley artifacts in `parley/` and keeps the localization files in their original `.lproj` folders.

## 2. Dry-Run Bulk TM Import

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/MyApp/parley" \
  --source-root "/path/to/MyApp" \
  --status approved \
  --dry-run
```

Review the `translation_memory` report.

Healthy production-corpus findings usually look like:

- high `imported_count`
- `missing_key` findings for partial locales
- zero `placeholder_mismatch`
- zero `extra_key`
- no parser failures
- no path conflicts

Exit code `1` is expected when target files are partial and missing canonical keys.

## 3. Add Locale Overrides

Some `.lproj` folders are ambiguous. Use `--locale-map` when you want a specific stored locale.

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/MyApp/parley" \
  --source-root "/path/to/MyApp" \
  --status approved \
  --locale-map bg=bg-BG \
  --locale-map hr=hr-HR \
  --locale-map mn=mn-MN \
  --locale-map sl=sl-SI \
  --dry-run
```

Run `parley locale list --query <language>` when you are unsure which code to use.

## 4. Apply Bulk TM Import

When the dry-run report looks right, remove `--dry-run`:

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/MyApp/parley" \
  --source-root "/path/to/MyApp" \
  --status approved \
  --locale-map bg=bg-BG \
  --locale-map hr=hr-HR \
  --locale-map mn=mn-MN \
  --locale-map sl=sl-SI
```

This writes:

- target records into `inventory.yaml`
- imported records into `translation-memory.sqlite`
- one `tm_import_lproj_dir` report

It does not rewrite any `.strings` files.

## 5. Validate Targets

```sh
PYTHONPATH=src python3 -m parley validate \
  --project-root "/path/to/MyApp/parley" \
  --no-authoritative
```

After a clean import, validation should usually mirror the TM import findings:

- missing keys for incomplete locales
- no placeholder mismatches
- no extra keys
- no parse errors

## 6. Prepare Context And Glossary

For context-aware translation:

```sh
PYTHONPATH=src python3 -m parley context validate \
  --project-root "/path/to/MyApp/parley"
```

Populate `context-anchor.yaml` for keys you want to translate. For a literal pass, add `--no-context` to translation commands.

For terminology:

```sh
PYTHONPATH=src python3 -m parley glossary init \
  --project-root "/path/to/MyApp/parley" \
  --with-example
```

Edit `glossary.yaml`, then validate:

```sh
PYTHONPATH=src python3 -m parley glossary validate \
  --project-root "/path/to/MyApp/parley"
```

## 7. Translate One Locale

Dry-run:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/MyApp/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/MyApp/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/MyApp/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/MyApp/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target
```

Existing production target-file translations are preserved. Missing keys are filled from TM first, then generated through the configured provider when needed.

## 8. Translate All Locales

Dry-run:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/MyApp/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Apply:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/MyApp/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target
```

Batch translation writes:

- one translation report per target locale
- one `translate_batch` roll-up report

The roll-up report is the fastest way to evaluate batch outcomes before applying.

## 9. Update Authoritative Source Later

When English changes:

1. Replace or update `en.lproj/Localizable.strings`.
2. Refresh the authoritative registration:

```sh
PYTHONPATH=src python3 -m parley localization add \
  "/path/to/MyApp/en.lproj/Localizable.strings" \
  --project-root "/path/to/MyApp/parley" \
  --locale en-US \
  --role authoritative
```

3. Validate context:

```sh
PYTHONPATH=src python3 -m parley context validate \
  --project-root "/path/to/MyApp/parley"
```

4. Run `translate-batch --dry-run`.
5. Review reports.
6. Apply batch translation.

Do not use `project init --force` for this update path; it replaces core artifacts and starts TM over.
