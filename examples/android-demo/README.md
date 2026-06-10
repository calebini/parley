# Android Demo Strings

Synthetic Android XML localization fixtures for Parley dry runs. These are fake product strings and safe to commit.

Files:

- `values/strings.xml`: authoritative source strings.
- `values-fr/strings.xml`: empty target fixture used by smoke tests.

The fixture includes Android-style `%1$s`, printf-style `%d`, brace placeholders, and XML escaping.

Minimal flow:

```sh
WORKDIR="$(mktemp -d /private/tmp/parley-android-demo.XXXXXX)"
cp -R examples/android-demo/. "$WORKDIR/"

PYTHONPATH=src python3 -m parley project init \
  --project-root "$WORKDIR" \
  --name "Pocket Tasks Android" \
  --authoritative "$WORKDIR/values/strings.xml" \
  --locale en-US \
  --format android_xml

PYTHONPATH=src python3 -m parley localization add \
  "$WORKDIR/values-fr/strings.xml" \
  --project-root "$WORKDIR" \
  --locale fr-FR \
  --format android_xml
```

Translate with the dummy provider:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "$WORKDIR" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider dummy \
  --no-context
```
