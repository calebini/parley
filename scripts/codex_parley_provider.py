#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


def main() -> int:
    request = _read_request()
    with tempfile.TemporaryDirectory() as tmp:
        schema_path = Path(tmp) / "parley-provider-response.schema.json"
        output_path = Path(tmp) / "codex-response.json"
        schema_path.write_text(json.dumps(_response_schema(), sort_keys=True), encoding="utf-8")
        completed = subprocess.run(
            [
                os.environ.get("PARLEY_CODEX_COMMAND", "codex"),
                "exec",
                "--cd",
                str(Path.cwd()),
                "-c",
                'web_search="disabled"',
                "-c",
                'model_reasoning_effort="medium"',
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ],
            input=_prompt(request),
            text=True,
            capture_output=True,
            check=False,
            timeout=int(os.environ.get("PARLEY_CODEX_TIMEOUT_SECONDS", "120")),
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            return completed.returncode
        if output_path.exists():
            sys.stdout.write(output_path.read_text(encoding="utf-8"))
            return 0
        sys.stdout.write(completed.stdout)
        return 0


def _read_request() -> dict[str, Any]:
    request_path = os.environ.get("PARLEY_REQUEST_PATH")
    if request_path:
        return json.loads(Path(request_path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _prompt(request: dict[str, Any]) -> str:
    return (
        "You are a Parley localization provider for a controlled local smoke test.\n"
        "Return exactly one JSON object matching the supplied schema.\n"
        "Translate each entry's source_text to the target_locale while preserving placeholders exactly.\n"
        "Do not include markdown, commentary, or extra fields.\n\n"
        "Parley provider request JSON:\n"
        f"{json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2)}\n"
    )


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "request_id", "provider_id", "status", "entries", "provider_metadata"],
        "properties": {
            "schema_version": {"type": "string", "const": "1.0"},
            "request_id": {"type": "string"},
            "provider_id": {"type": "string"},
            "status": {"type": "string", "enum": ["ok", "partial", "failed"]},
            "provider_metadata": {
                "type": ["object", "null"],
                "additionalProperties": False,
            },
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "status", "translated_text", "failure_reason"],
                    "properties": {
                        "key": {"type": "string"},
                        "status": {"type": "string", "enum": ["translated", "refused", "failed"]},
                        "translated_text": {"type": ["string", "null"]},
                        "failure_reason": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
