# Provider CLI Adapter Notes

Parley's first real-provider path uses the generic `command-json` provider. The provider command is responsible for reading a Parley provider request and returning a schema-valid Parley provider response.

For now, keep real LLM provider work behind explicit operator configuration and test it only with dummy/demo strings.

## Current Supported Modes

The implemented command-backed provider supports:

- `--provider command-json`
- `--provider-command <executable>`
- `--provider-request-delivery stdin_json`
- `--provider-request-delivery output_file`
- `--provider-response-mode stdout_json`
- `--provider-response-mode stdout_json_envelope`
- `--provider-response-mode output_file_json`

The default transport is `stdin_json` request delivery plus `stdout_json` response parsing.

## Codex-Shaped Envelope

For Codex-like command wrappers, prefer:

```text
--provider command-json
--provider-request-delivery stdin_json
--provider-response-mode stdout_json_envelope
--provider-timeout-seconds 120
```

`stdout_json_envelope` accepts either:

- a top-level `structured_output` object containing the Parley provider response, or
- a top-level `result` string containing the Parley provider response as JSON text.

This matches the envelope shapes used by fake Codex-shaped smoke tests without requiring the real Codex CLI yet.

## Local Codex Wrapper Smoke

The repo includes an experimental local wrapper:

```text
scripts/codex_parley_provider.py
```

Use it only with dummy/demo strings while the provider surface is still settling:

```text
PYTHONPATH=src python3 -m parley translate \
  --project-root <demo-project> \
  --target-locale fr-FR \
  --reuse-mode provider_only \
  --provider command-json \
  --provider-command ./scripts/codex_parley_provider.py \
  --provider-response-mode stdout_json \
  --provider-timeout-seconds 180
```

The wrapper reads Parley's provider request, calls `codex exec` with a strict Parley provider-response schema, and prints the resulting JSON response for the generic `command-json` adapter to validate.

Environment knobs:

- `PARLEY_CODEX_COMMAND`: defaults to `codex`
- `PARLEY_CODEX_TIMEOUT_SECONDS`: defaults to `120`

## File-Backed Transport

For CLIs that need file paths instead of stdin/stdout JSON:

```text
--provider command-json
--provider-request-delivery output_file
--provider-response-mode output_file_json
```

Parley sets:

- `PARLEY_REQUEST_PATH`
- `PARLEY_RESPONSE_PATH`

Transport files are written under `.parley/provider-io/` and cleaned up after the adapter reads the result. They are not durable Parley artifacts.

## Deferred

Still deferred:

- real `codex-cli` named provider wrapper
- real `claude-cli` named provider wrapper
- hosted API providers
- production-string smoke tests
- retry/backoff policy
- interactive auth flows
