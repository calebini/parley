# Parley CLI MVP Walkthrough

This walkthrough uses synthetic iOS strings from `examples/ios-demo`. It does not use production strings or external providers.

Run from the repository root:

```sh
WORKDIR="$(mktemp -d /private/tmp/parley-ios-demo.XXXXXX)"
cp -R examples/ios-demo/. "$WORKDIR/"
```

Initialize a Parley project:

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "$WORKDIR" \
  --name "Pocket Tasks" \
  --authoritative "$WORKDIR/en.lproj/Localizable.strings" \
  --locale en-US
```

Context for local MVP testing:

`project init` scaffolds `context-anchor.yaml` with one blank context entry for every canonical key. For context-aware translation, replace those blank values with meaningful product/context descriptions. This walkthrough uses `--no-context` below to exercise the literal/dummy-provider path.

Create and add an empty target localization:

```sh
mkdir -p "$WORKDIR/fr-generated.lproj"
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/fr-generated.lproj/Localizable.strings" \
  --project-root "$WORKDIR" \
  --locale fr-FR
```

The empty target reports blocking validation findings because required keys are missing. That is expected; translation fills the target next.

For existing target files with stable translations, import them into translation memory:

```sh
PYTHONPATH=src python3 -m parley tm import-target \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --status reviewed
```

Run deterministic dummy translation:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider dummy \
  --no-context
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

The second translate should reuse all generated entries from `translation-memory.sqlite` without provider work.

## Translation Report Checks

Translation reports are written under:

```text
$WORKDIR/reports/translation/
```

For the dummy-provider run, the report summary should show:

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

For the follow-up `tm_only` run, the report summary should show:

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
