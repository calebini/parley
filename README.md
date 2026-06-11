# Parley

Parley is a project-first localization CLI for teams that want translation work to be repeatable, inspectable, and safe to run against real string files.

It turns a localization directory into a durable project with an authoritative source file, canonical key inventory, context anchors, glossary terms, translation memory, validation reports, and deterministic write-back behavior.

## What Parley Does

- Initializes projects from authoritative iOS `.strings` or Android XML string resources.
- Registers target localization files and validates them against the authoritative source.
- Imports existing human/stable translations into SQLite translation memory.
- Bulk-imports production iOS `.lproj` corpora into project inventory and TM.
- Translates one target or all registered targets.
- Reuses approved/imported TM before calling a provider.
- Supports `dummy`, `command-json`, Codex CLI, and Claude Code provider wrappers.
- Applies glossary constraints during provider-backed translation.
- Writes JSON reports for validation, lint, TM import, translation, glossary, and context checks.
- Supports dry-run workflows before mutating target files or TM.

## Core Concepts

- **Authoritative localization:** the source file that defines the canonical key set and placeholder signatures.
- **Inventory:** registered localization files, their locales, roles, formats, and paths.
- **Translation memory:** reusable target values keyed by project, source locale, target locale, key, source hash, and placeholder signature.
- **Context anchor:** human-authored project and per-key context used for context-aware translation.
- **Glossary:** human-authored terminology rules and preferred/prohibited target terms.
- **Reports:** deterministic JSON artifacts that explain what was validated, imported, reused, generated, written, or skipped.

## Install For Local Development

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Run tests:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Common Workflows

### Start A New Project

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "/path/to/App/parley" \
  --name "My App" \
  --authoritative "/path/to/App/en.lproj/Localizable.strings" \
  --locale en-US
```

This keeps Parley artifacts under `/path/to/App/parley` while inventory paths still point at localization files under `/path/to/App`.

### Import An Existing iOS Corpus

For a production directory with many sibling `.lproj` folders:

```sh
PYTHONPATH=src python3 -m parley tm import-lproj-dir \
  --project-root "/path/to/App/parley" \
  --source-root "/path/to/App" \
  --status approved \
  --dry-run
```

Review the `translation_memory` report, add any needed `--locale-map LPROJ=LOCALE` overrides, then rerun without `--dry-run`. The command registers targets and imports compatible existing strings into TM without rewriting any `.strings` files.

### Translate One Locale

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

Remove `--dry-run` after reviewing the report.

### Translate All Registered Targets

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --target-conflict-mode preserve_target \
  --dry-run
```

Batch translation writes normal per-target translation reports plus one `translate_batch` roll-up report. Add repeated `--target-locale LOCALE` flags to restrict a run.

### Validate Targets

```sh
PYTHONPATH=src python3 -m parley validate \
  --project-root "/path/to/App/parley" \
  --no-authoritative
```

Validation reports missing keys, extra keys, placeholder mismatches, parse errors, IO errors, and glossary findings.

### Lint Release Polish

Run a high-signal lint audit before sharing or shipping generated targets:

```sh
PYTHONPATH=src python3 -m parley lint audit \
  --project-root "/path/to/App/parley"
```

`lint audit` reports localization polish issues such as mojibake/encoding artifacts, coverage drift, and placeholder drift under `reports/lint/`.
By default it audits localization files only. Use `--scope all` to include translation memory records.

Apply only high-confidence mechanical fixes, such as mojibake repair, with a dry-run first:

```sh
PYTHONPATH=src python3 -m parley lint fix \
  --project-root "/path/to/App/parley" \
  --dry-run

PYTHONPATH=src python3 -m parley lint fix \
  --project-root "/path/to/App/parley"
```

`lint fix` updates affected target files and matching current TM records, then re-audits before writing its report.

## Provider Configuration

Provider profiles live in `parley.yaml`:

```yaml
defaults:
  provider: codex
  report_format: "json"
providers:
  codex:
    type: command-json
    command: /path/to/scripts/codex_parley_provider.py
    timeout_seconds: 180
    request_delivery: stdin_json
    response_mode: stdout_json
```

Claude Code uses the same `command-json` boundary:

```yaml
providers:
  claude:
    type: command-json
    command: /path/to/scripts/claude_parley_provider.py
    timeout_seconds: 180
    request_delivery: stdin_json
    response_mode: stdout_json
```

See [Provider CLI Adapters](docs/PROVIDER_CLI_ADAPTERS.md) for details.

## Documentation

- [User Guide](docs/USER_GUIDE.md)
- [Production iOS Corpus Workflow](docs/PRODUCTION_IOS_CORPUS_WORKFLOW.md)
- [CLI Demo Walkthrough](docs/CLI_MVP_WALKTHROUGH.md)
- [Provider CLI Adapters](docs/PROVIDER_CLI_ADAPTERS.md)
- [High-Level Architecture](docs/hld-architecture.md)
- [Specification Index](docs/specs/00-spec-index.md)

## Status

Parley is an active MVP. The current implementation is usable for project-mode localization workflows with local artifacts, TM reuse, glossary enforcement, and command-backed providers. The next frontier is better packaging, review/approval ergonomics, richer provider quality checks, and broader format coverage.
