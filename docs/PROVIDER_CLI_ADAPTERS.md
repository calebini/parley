# Provider CLI Adapters

Parley uses a generic `command-json` provider boundary for local LLM CLIs and other provider commands.

The provider command receives a Parley translation request and returns a schema-valid Parley translation response. Parley owns TM reuse, glossary resolution, placeholder validation, reports, and write-back. The provider owns only the generated translation text for requested entries.

## Built-In Provider IDs

- `dummy`: deterministic local provider for tests and demos.
- `command-json`: generic command-backed provider.

Named provider profiles are configured in `parley.yaml`.

## Recommended Project Configuration

Codex:

```yaml
defaults:
  provider: codex
  report_format: "json"
providers:
  codex:
    type: command-json
    command: /path/to/parley/scripts/codex_parley_provider.py
    timeout_seconds: 180
    request_delivery: stdin_json
    response_mode: stdout_json
```

Claude Code:

```yaml
defaults:
  provider: claude
  report_format: "json"
providers:
  claude:
    type: command-json
    command: /path/to/parley/scripts/claude_parley_provider.py
    timeout_seconds: 180
    request_delivery: stdin_json
    response_mode: stdout_json
```

With `defaults.provider` configured, translation commands can omit `--provider`.

## Single Target Translation

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/App/parley" \
  --target-locale fr-FR \
  --target-path "/path/to/App/fr.lproj/Localizable.strings" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --dry-run
```

Remove `--dry-run` to apply.

## Batch Translation

```sh
PYTHONPATH=src python3 -m parley translate-batch \
  --project-root "/path/to/App/parley" \
  --reuse-mode tm_then_provider \
  --write-order authoritative \
  --dry-run
```

Batch translation uses the same provider profile for each selected target and writes both per-target translation reports and a roll-up report.

## Direct Command-JSON Smoke

You can bypass named provider config for a quick smoke:

```sh
PYTHONPATH=src python3 -m parley translate \
  --project-root "/path/to/demo-project" \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider command-json \
  --provider-command ./scripts/codex_parley_provider.py \
  --provider-request-delivery stdin_json \
  --provider-response-mode stdout_json \
  --provider-timeout-seconds 180 \
  --no-context \
  --dry-run
```

## Supported Transport Modes

Request delivery:

- `stdin_json`: provider request JSON is written to stdin.
- `output_file`: provider request JSON is written to `PARLEY_REQUEST_PATH`.

Response modes:

- `stdout_json`: provider prints the Parley provider response JSON to stdout.
- `stdout_json_envelope`: provider prints a wrapper object containing either `structured_output` or a JSON string in `result`.
- `output_file_json`: provider writes response JSON to `PARLEY_RESPONSE_PATH`.

The default named-profile transport is `stdin_json` plus `stdout_json`.

## Provider Diagnostics

When provider-backed translation fails, the translation report records:

- `provider_status`
- `provider_failure_category`
- bounded `provider_diagnostics`

For command-backed providers, diagnostics include process telemetry such as exit code, duration, timeout state, and stdout/stderr tails. Parley does not echo the full provider request payload into normal diagnostics.

## Wrapper Scripts

The repository includes:

- `scripts/codex_parley_provider.py`
- `scripts/claude_parley_provider.py`
- `scripts/smoke_codex_provider.sh`

The wrappers are intentionally thin. They adapt Codex/Claude CLI output into Parley's provider response schema.

Codex environment knobs:

- `PARLEY_CODEX_COMMAND`: defaults to `codex`
- `PARLEY_CODEX_TIMEOUT_SECONDS`: defaults to `120`

To run the opt-in Codex smoke against synthetic strings:

```sh
PARLEY_RUN_CODEX_SMOKE=1 scripts/smoke_codex_provider.sh
```

## Safety Notes

- Start with `--dry-run`.
- Use demo strings first when testing a new provider profile.
- Keep provider commands explicit in `parley.yaml`.
- Use `tm_then_provider` for production projects so approved/imported TM is reused before provider generation.
- Use `--no-provider` when you want to verify which keys would need provider work without making calls.
