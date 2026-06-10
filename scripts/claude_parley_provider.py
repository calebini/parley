#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def main() -> int:
    request = _read_request()
    prompt = _prompt(request)
    completed = subprocess.run(
        _claude_args(_response_schema()),
        cwd=Path.cwd(),
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        timeout=int(os.environ.get("PARLEY_CLAUDE_TIMEOUT_SECONDS", "120")),
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return completed.returncode
    try:
        artifact = _parse_claude_output(completed.stdout)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(json.dumps(artifact, ensure_ascii=False, sort_keys=True))
    sys.stdout.write("\n")
    return 0


def _claude_args(schema: dict[str, Any]) -> list[str]:
    args = [
        os.environ.get("PARLEY_CLAUDE_COMMAND", "claude"),
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--json-schema",
        json.dumps(schema, sort_keys=True),
    ]
    model = os.environ.get("PARLEY_CLAUDE_MODEL")
    if model:
        args.extend(["--model", model])
    return args


def _read_request() -> dict[str, Any]:
    request_path = os.environ.get("PARLEY_REQUEST_PATH")
    if request_path:
        return json.loads(Path(request_path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def _parse_claude_output(content: str) -> dict[str, Any]:
    envelope = _parse_json_value(content, "claude stdout")
    if isinstance(envelope, list):
        for event in reversed(envelope):
            if not isinstance(event, dict):
                continue
            structured_output = event.get("structured_output")
            if isinstance(structured_output, dict):
                return structured_output
            result = event.get("result")
            if isinstance(result, dict):
                return result
            if isinstance(result, str) and result.strip():
                return _parse_json_object(result, "claude result")
            message = event.get("message")
            if isinstance(message, dict):
                content_items = message.get("content")
                if isinstance(content_items, list):
                    for item in content_items:
                        if isinstance(item, dict) and item.get("name") == "StructuredOutput":
                            structured = item.get("input")
                            if isinstance(structured, dict):
                                return structured
        raise ValueError("claude stdout did not include structured output")
    if not isinstance(envelope, dict):
        raise ValueError("claude stdout JSON is not an object")
    structured_output = envelope.get("structured_output")
    if isinstance(structured_output, dict):
        return structured_output
    result = envelope.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return _parse_json_object(result, "claude result")
    return envelope


def _parse_json_value(content: str, source: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source} is not JSON") from exc


def _parse_json_object(content: str, source: str) -> dict[str, Any]:
    value = _parse_json_value(content, source)
    if not isinstance(value, dict):
        raise ValueError(f"{source} JSON is not an object")
    return value


def _prompt(request: dict[str, Any]) -> str:
    return (
        "You are a Parley localization provider.\n"
        "Return exactly one JSON object matching the supplied schema.\n"
        "Translate each entry's source_text to the target_locale while preserving placeholders exactly.\n"
        "Respect project_context, context_description, glossary_constraints, and translation_memory_candidates.\n"
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
