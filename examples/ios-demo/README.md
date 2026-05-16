# iOS Demo Strings

Synthetic localization fixtures for Parley dry runs. These are intentionally fake product strings and safe to commit.

Files:

- `en.lproj/Localizable.strings`: authoritative source strings.
- `fr-clean.lproj/Localizable.strings`: target strings with matching keys and placeholders.
- `fr-broken.lproj/Localizable.strings`: target strings with a missing key, an extra key, and placeholder mismatches.

Suggested dry-run flow:

1. Copy this directory to a temporary project root.
2. Run `parley project init` with `en.lproj/Localizable.strings` as the authoritative localization.
3. Populate `context-anchor.yaml` with non-empty per-key context.
4. Add an empty target localization.
5. Run `parley translate --target-locale fr-FR --reuse-mode provider_only --provider dummy`.
6. Run `parley validate --no-authoritative`.
7. Clear the target file and run `parley translate --target-locale fr-FR --reuse-mode tm_only` to verify translation-memory reuse.
