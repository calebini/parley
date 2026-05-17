from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parley.command_json import CommandJsonAdapter, CommandJsonConfig, CommandJsonError
from parley.hashing import sha256_canonical_json


@dataclass(frozen=True)
class TranslationRequest:
    key: str
    source_value: str
    source_locale: str
    target_locale: str
    placeholder_signature: str


@dataclass(frozen=True)
class TranslationResponse:
    key: str
    target_value: str


class TranslationProvider:
    provider_id = "provider"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        raise NotImplementedError


class DummyTranslationProvider(TranslationProvider):
    provider_id = "dummy"

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        return TranslationResponse(
            key=request.key,
            target_value=f"[{request.target_locale}] {request.source_value}",
        )


class ProviderInvocationError(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


class ProviderConfigurationError(ValueError):
    pass


class CommandJsonTranslationProvider(TranslationProvider):
    provider_id = "command-json"

    def __init__(self, *, command: str, cwd: Path, timeout_seconds: int = 30) -> None:
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        request_payload = _translation_request_payload(
            provider_id=self.provider_id,
            request=request,
        )
        adapter = CommandJsonAdapter(
            CommandJsonConfig(
                command=self.command,
                cwd=self.cwd,
                timeout_seconds=self.timeout_seconds,
            ),
            validator=lambda artifact: _validate_translation_response(artifact, request_payload, request.key),
        )
        try:
            result = adapter.invoke(request_payload)
        except CommandJsonError as exc:
            raise ProviderInvocationError(exc.classification, str(exc)) from exc
        entry = result.artifact["entries"][0]
        if entry["status"] != "translated":
            raise ProviderInvocationError("provider_failed", entry["failure_reason"] or "provider did not translate entry")
        return TranslationResponse(key=request.key, target_value=entry["translated_text"])


def translation_provider(
    provider_id: str,
    *,
    provider_command: str | None = None,
    project_root: Path | None = None,
    timeout_seconds: int = 30,
) -> TranslationProvider:
    if provider_id == "dummy":
        return DummyTranslationProvider()
    if provider_id == "command-json":
        if provider_command is None:
            raise ProviderConfigurationError("provider command is required for command-json")
        if timeout_seconds <= 0:
            raise ProviderConfigurationError("provider timeout must be a positive integer")
        return CommandJsonTranslationProvider(
            command=provider_command,
            cwd=project_root or Path.cwd(),
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"unsupported translation provider: {provider_id}")


def _translation_request_payload(*, provider_id: str, request: TranslationRequest) -> dict[str, Any]:
    entry = {
        "key": request.key,
        "source_locale": request.source_locale,
        "target_locale": request.target_locale,
        "source_text": request.source_value,
        "protected_text": request.source_value,
        "placeholder_tokens": [],
        "context_description": None,
        "glossary_constraints": [],
        "translation_memory_candidates": [],
    }
    request_id = "parley_" + sha256_canonical_json(
        {
            "operation": "translate_batch",
            "provider_id": provider_id,
            "source_locale": request.source_locale,
            "target_locale": request.target_locale,
            "entries": [entry],
        }
    )[:32]
    return {
        "schema_version": "1.0",
        "request_id": request_id,
        "operation": "translate_batch",
        "provider_id": provider_id,
        "source_locale": request.source_locale,
        "target_locale": request.target_locale,
        "project_context": {},
        "entries": [entry],
    }


def _validate_translation_response(artifact: dict[str, Any], request_payload: dict[str, Any], expected_key: str) -> None:
    required = {"schema_version", "request_id", "provider_id", "status", "entries", "provider_metadata"}
    missing = sorted(required - set(artifact))
    if missing:
        raise ValueError(f"provider response missing required fields: {', '.join(missing)}")
    if artifact["schema_version"] != "1.0":
        raise ValueError("provider response schema_version must be 1.0")
    if artifact["request_id"] != request_payload["request_id"]:
        raise ValueError("provider response request_id does not match request")
    if artifact["provider_id"] != request_payload["provider_id"]:
        raise ValueError("provider response provider_id does not match request")
    if artifact["status"] not in {"ok", "partial", "failed"}:
        raise ValueError("provider response status is invalid")
    entries = artifact["entries"]
    if not isinstance(entries, list):
        raise ValueError("provider response entries must be an array")
    if len(entries) != 1:
        raise ValueError("provider response must contain exactly one entry")
    entry = entries[0]
    if not isinstance(entry, dict):
        raise ValueError("provider response entry must be an object")
    if entry.get("key") != expected_key:
        raise ValueError("provider response entry key does not match request")
    if entry.get("status") not in {"translated", "refused", "failed"}:
        raise ValueError("provider response entry status is invalid")
    translated_text = entry.get("translated_text")
    failure_reason = entry.get("failure_reason")
    if entry["status"] == "translated":
        if not isinstance(translated_text, str):
            raise ValueError("translated provider entry must include string translated_text")
        if failure_reason is not None:
            raise ValueError("translated provider entry must not include failure_reason")
    else:
        if translated_text is not None:
            raise ValueError("failed provider entry must not include translated_text")
        if not isinstance(failure_reason, str) or not failure_reason:
            raise ValueError("failed provider entry must include failure_reason")
