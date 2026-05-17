# Android Demo Strings

Synthetic Android XML localization fixtures for Parley dry runs. These are fake product strings and safe to commit.

Files:

- `values/strings.xml`: authoritative source strings.
- `values-fr/strings.xml`: empty target fixture used by the end-to-end smoke test.

The fixture is intentionally small but includes Android-style `%1$s`, printf-style `%d`, brace placeholders, and XML escaping.
