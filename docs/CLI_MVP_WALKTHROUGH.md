# CLI Demo Walkthrough

This walkthrough uses synthetic iOS strings from `examples/ios-demo`. It is safe for local smoke testing and does not require external providers.

For production usage, start with [User Guide](USER_GUIDE.md) or [Production iOS Corpus Workflow](PRODUCTION_IOS_CORPUS_WORKFLOW.md).

## 1. Create A Temporary Demo Project

```sh
WORKDIR="$(mktemp -d /private/tmp/parley-ios-demo.XXXXXX)"
cp -R examples/ios-demo/. "$WORKDIR/"
```

```sh
PYTHONPATH=src python3 -m parley project init \
  --project-root "$WORKDIR" \
  --name "Pocket Tasks" \
  --authoritative "$WORKDIR/en.lproj/Localizable.strings" \
  --locale en-US
```

## 2. Check Blank Context

```sh
PYTHONPATH=src python3 -m parley context validate \
  --project-root "$WORKDIR"
```

Fresh projects have blank per-key context entries. This demo uses `--no-context` during translation to exercise the literal provider path.

## 3. Add An Empty Target

```sh
mkdir -p "$WORKDIR/fr-generated.lproj"
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/fr-generated.lproj/Localizable.strings" \
  --project-root "$WORKDIR" \
  --locale fr-FR
```

The empty target should report missing-key findings. Translation fills it next.

## 4. Translate With The Dummy Provider

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider dummy \
  --no-context
```

Validate:

```sh
PYTHONPATH=src python3 -m parley validate \
  --project-root "$WORKDIR" \
  --no-authoritative
```

## 5. Verify TM Reuse

Clear the target file:

```sh
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"
```

Refill from TM only:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode tm_only \
  --no-context
```

The report should show `reused_count` equal to the key count and `provider_status: "not_applicable"`.

## 6. Try Batch Translation

Create another empty target:

```sh
mkdir -p "$WORKDIR/de-generated.lproj"
: > "$WORKDIR/de-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/de-generated.lproj/Localizable.strings" \
  --project-root "$WORKDIR" \
  --locale de-DE
```

Dry-run all registered targets:

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "$WORKDIR" \
  --reuse-mode provider_only \
  --provider dummy \
  --no-context \
  --dry-run
```

Review the per-target reports and the `translate_batch` roll-up report under:

```text
$WORKDIR/reports/translation/
```
