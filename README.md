# Parley

Parley is a project-first localization CLI for teams that want translation workflows to be repeatable, inspectable, and safe to run against real string files.

Most translation tooling treats localization as a one-off file conversion problem: send strings out, get strings back, hope the placeholders survived, and repeat the same work again later. Parley takes a different path. It turns a localization directory into a small, durable project with an authoritative source file, canonical key inventory, context anchors, translation memory, validation reports, and deterministic write-back behavior.

The result is a translation workflow that remembers what it has done, explains what changed, and gives humans and CI enough structure to trust the output.

## Why Parley Exists

Localization gets risky when context disappears.

A short UI string like `Sync failed` can mean different things depending on product surface, user state, tone, platform convention, and surrounding copy. A placeholder like `%@` or `%d` is not decoration; if it is changed, reordered incorrectly, or dropped, the app can break. A translation that was approved last week should not be casually regenerated today just because a batch command ran again.

Parley is built around those realities:

- **Context should be durable.** Per-key context belongs in the project, not only in an ephemeral prompt.
- **The source of truth should be explicit.** One authoritative localization drives the canonical key inventory.
- **Validation should be structured.** Missing keys, extra keys, parser failures, placeholder mismatches, and provider failures are reported with stable categories.
- **Translation memory should be first-class.** Generated or reviewed translations become reusable project assets.
- **Writes should be inspectable.** Reports say whether the target file changed, whether translation memory changed, whether a provider was used, and whether a run was dry-run only.

## Current MVP Capabilities

Parley currently supports a local MVP workflow:

- Initialize a Parley project from an authoritative localization file.
- Track project artifacts:
  - `parley.yaml`
  - `inventory.yaml`
  - `canonical-inventory.json`
  - `context-anchor.yaml`
  - `glossary.yaml`
  - `translation-memory.sqlite`
  - JSON reports under `reports/`
- Parse, validate, translate, and reuse iOS `.strings` files in an end-to-end demo flow.
- Parse, validate, translate, and reuse Android XML string resources in an end-to-end demo flow.
- Add target localizations to project inventory.
- Validate targets against the canonical source:
  - missing keys
  - extra keys
  - placeholder mismatches
  - parser and IO failures
- Seed placeholder context for local MVP dry runs.
- Translate via a deterministic local `dummy` provider.
- Reuse translations from SQLite translation memory.
- Write target localization files atomically.
- Produce deterministic validation and translation reports.

The dummy provider is intentionally boring. It exists so the full workflow can be tested without production strings, external APIs, credentials, network access, or cost.

## The Workflow

Parley’s happy path looks like this:

```text
project init
  -> context seed
  -> localization add
  -> translate
  -> validate
  -> translate again with TM reuse
```

That loop is the heart of the tool. The first translation can generate target strings. Later runs can reuse translation memory instead of regenerating work that is already known.

## Quick Start

From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Run the test suite:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

Try the synthetic iOS demo:

```sh
WORKDIR="$(mktemp -d /private/tmp/parley-ios-demo.XXXXXX)"
cp -R examples/ios-demo/. "$WORKDIR/"
```

Initialize the project:

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "$WORKDIR" \
  --name "Pocket Tasks" \
  --authoritative "$WORKDIR/en.lproj/Localizable.strings" \
  --locale en-US
```

Seed placeholder context:

```sh
PYTHONPATH=src python3 -m parley context seed \
  --project-root "$WORKDIR" \
  --mode placeholder
```

Create and add an empty French target:

```sh
mkdir -p "$WORKDIR/fr-generated.lproj"
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/fr-generated.lproj/Localizable.strings" \
  --project-root "$WORKDIR" \
  --locale fr-FR
```

The empty target should report blocking validation findings. That is expected; translation fills it next.

Run deterministic local translation:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider dummy
```

Validate the generated target:

```sh
PYTHONPATH=src python3 -m parley validate \
  --project-root "$WORKDIR" \
  --no-authoritative
```

Verify translation-memory reuse:

```sh
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode tm_only
```

The second translate should refill the target from `translation-memory.sqlite` without provider work.

The same project workflow is also covered by `examples/android-demo`, which exercises Android XML parsing, XML escaping, placeholder preservation, validation, translation write-back, and translation-memory reuse.

## Reports You Can Trust

Parley writes JSON reports so humans and CI can inspect what happened.

Translation reports include summary fields such as:

```json
{
  "generated_count": 8,
  "reused_count": 0,
  "written_target": true,
  "tm_written": true,
  "dry_run": false,
  "provider_id": "dummy",
  "provider_status": "used"
}
```

For a follow-up translation-memory-only run, the same report surface shows reuse clearly:

```json
{
  "generated_count": 0,
  "reused_count": 8,
  "written_target": true,
  "tm_written": true,
  "dry_run": false,
  "provider_id": "dummy",
  "provider_status": "not_applicable"
}
```

This is the difference between “the command exited 0” and “we know exactly what changed.”

## Project Artifacts

A Parley project is a directory with durable localization state:

```text
parley.yaml
inventory.yaml
canonical-inventory.json
context-anchor.yaml
glossary.yaml
translation-memory.sqlite
reports/
```

The authoritative localization defines the canonical key set. Target localizations are validated against that baseline. Translation memory stores reusable target values keyed by project, source locale, target locale, canonical key, source hash, and placeholder signature.

## Design Principles

### Project-first, not file-first

The MVP intentionally centers project mode. Direct file-to-file translation is deferred because it lacks durable context, inventory, report rooting, and translation memory continuity.

### Context is an artifact

Parley treats context as something worth storing and reviewing. The current `context seed` command creates placeholder context for local dry runs; future provider-backed context generation can fill the same artifact with richer data.

### Translation memory is a quality asset

TM is not just a cache. It is where generated, reviewed, imported, and eventually human-approved translations can become durable candidates for reuse.

### Reports are part of the product

Every serious localization workflow needs auditability. Parley’s reports are designed to answer practical operator questions: what failed, what changed, what was reused, whether provider work happened, and whether write-back occurred.

### Local first

The current MVP runs entirely locally with no external dependencies. External provider integrations should fit behind provider interfaces without changing the core workflow.

## What Is Still Coming

Parley is early. The current implementation proves the project workflow and local translation loop. Upcoming areas include:

- Real provider adapters.
- Rich context generation.
- Human review and approval commands.
- Richer Android XML fixtures and edge-case coverage.
- Glossary enforcement.
- Confidence scoring and review evidence.
- Import/export for translation memory.
- Better packaging and terminal UX.

## Documentation

- [CLI MVP Walkthrough](docs/CLI_MVP_WALKTHROUGH.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [High-Level Architecture](docs/hld-architecture.md)
- [Specification Index](docs/specs/00-spec-index.md)

## Development

Run all tests:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

Inspect the CLI:

```sh
PYTHONPATH=src python3 -m parley --help
PYTHONPATH=src python3 -m parley translate --help
PYTHONPATH=src python3 -m parley context seed --help
```

## Status

Parley is an MVP implementation under active development. The current emphasis is correctness, deterministic artifacts, and a coherent project workflow before adding real external translation providers.
