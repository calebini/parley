# iOS Demo Strings

Synthetic localization fixtures for Parley dry runs. These are fake product strings and safe to commit.

Files:

- `en.lproj/Localizable.strings`: authoritative source strings.
- `fr-clean.lproj/Localizable.strings`: complete target strings with matching keys and placeholders.
- `fr-broken.lproj/Localizable.strings`: target strings with missing keys, an extra key, and placeholder mismatches.

Suggested flow:

```sh
WORKDIR="$(mktemp -d /private/tmp/parley-ios-demo.XXXXXX)"
cp -R examples/ios-demo/. "$WORKDIR/"

PYTHONPATH=src python3 -m parley project init \
  --project-root "$WORKDIR" \
  --name "Pocket Tasks" \
  --authoritative "$WORKDIR/en.lproj/Localizable.strings" \
  --locale en-US
```

Add an empty target and translate with the dummy provider:

```sh
mkdir -p "$WORKDIR/fr-generated.lproj"
: > "$WORKDIR/fr-generated.lproj/Localizable.strings"

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/fr-generated.lproj/Localizable.strings" \
  --project-root "$WORKDIR" \
  --locale fr-FR

PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider dummy \
  --no-context
```

For a fuller walkthrough, see `docs/CLI_MVP_WALKTHROUGH.md`.
