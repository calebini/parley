from __future__ import annotations

from dataclasses import dataclass


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


def translation_provider(provider_id: str) -> TranslationProvider:
    if provider_id == "dummy":
        return DummyTranslationProvider()
    raise ValueError(f"unsupported translation provider: {provider_id}")
