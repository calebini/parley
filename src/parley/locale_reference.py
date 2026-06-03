from __future__ import annotations

from parley.validation import CommandResult


COMMON_LOCALES = [
    ("Arabic", "ar", "Arabic"),
    ("Arabic (Egypt)", "ar-EG", "Arabic, Egypt"),
    ("Arabic (Saudi Arabia)", "ar-SA", "Arabic, Saudi Arabia"),
    ("Chinese (Simplified)", "zh-Hans", "Simplified Chinese"),
    ("Chinese (Simplified, China)", "zh-Hans-CN", "Simplified Chinese, China"),
    ("Chinese (Traditional)", "zh-Hant", "Traditional Chinese"),
    ("Chinese (Traditional, Taiwan)", "zh-Hant-TW", "Traditional Chinese, Taiwan"),
    ("Czech", "cs-CZ", "Czech, Czechia"),
    ("Danish", "da-DK", "Danish, Denmark"),
    ("Dutch", "nl-NL", "Dutch, Netherlands"),
    ("Dutch (Belgium)", "nl-BE", "Dutch, Belgium"),
    ("English (Australia)", "en-AU", "English, Australia"),
    ("English (Canada)", "en-CA", "English, Canada"),
    ("English (United Kingdom)", "en-GB", "English, United Kingdom"),
    ("English (United States)", "en-US", "English, United States"),
    ("Finnish", "fi-FI", "Finnish, Finland"),
    ("French", "fr-FR", "French, France"),
    ("French (Canada)", "fr-CA", "French, Canada"),
    ("German", "de-DE", "German, Germany"),
    ("German (Austria)", "de-AT", "German, Austria"),
    ("German (Switzerland)", "de-CH", "German, Switzerland"),
    ("Greek", "el-GR", "Greek, Greece"),
    ("Hebrew", "he-IL", "Hebrew, Israel"),
    ("Hindi", "hi-IN", "Hindi, India"),
    ("Hungarian", "hu-HU", "Hungarian, Hungary"),
    ("Indonesian", "id-ID", "Indonesian, Indonesia"),
    ("Italian", "it-IT", "Italian, Italy"),
    ("Japanese", "ja-JP", "Japanese, Japan"),
    ("Korean", "ko-KR", "Korean, South Korea"),
    ("Malay", "ms-MY", "Malay, Malaysia"),
    ("Norwegian Bokmal", "nb-NO", "Norwegian Bokmal, Norway"),
    ("Polish", "pl-PL", "Polish, Poland"),
    ("Portuguese (Brazil)", "pt-BR", "Portuguese, Brazil"),
    ("Portuguese (Portugal)", "pt-PT", "Portuguese, Portugal"),
    ("Romanian", "ro-RO", "Romanian, Romania"),
    ("Russian", "ru-RU", "Russian, Russia"),
    ("Slovak", "sk-SK", "Slovak, Slovakia"),
    ("Spanish", "es-ES", "Spanish, Spain"),
    ("Spanish (Latin America)", "es-419", "Spanish, Latin America"),
    ("Spanish (Mexico)", "es-MX", "Spanish, Mexico"),
    ("Swedish", "sv-SE", "Swedish, Sweden"),
    ("Thai", "th-TH", "Thai, Thailand"),
    ("Turkish", "tr-TR", "Turkish, Turkey"),
    ("Ukrainian", "uk-UA", "Ukrainian, Ukraine"),
    ("Vietnamese", "vi-VN", "Vietnamese, Vietnam"),
]

DEFAULT_REGION_BY_LANGUAGE = {
    "ar": "SA",
    "cs": "CZ",
    "da": "DK",
    "de": "DE",
    "el": "GR",
    "en": "US",
    "es": "ES",
    "fi": "FI",
    "fr": "FR",
    "he": "IL",
    "hi": "IN",
    "hu": "HU",
    "id": "ID",
    "it": "IT",
    "ja": "JP",
    "ko": "KR",
    "ms": "MY",
    "nb": "NO",
    "nl": "NL",
    "pl": "PL",
    "pt": "BR",
    "ro": "RO",
    "ru": "RU",
    "sk": "SK",
    "sv": "SE",
    "th": "TH",
    "tr": "TR",
    "uk": "UA",
    "vi": "VN",
}


def locale_reference_list(*, query: str | None) -> CommandResult:
    normalized_query = _lower_ascii(query or "").strip()
    query_terms = [term for term in normalized_query.split() if term]
    rows = []
    for language, locale, notes in COMMON_LOCALES:
        stored_locale = _lower_ascii(locale)
        haystack = _lower_ascii(" ".join([language, locale, stored_locale, notes]))
        if query_terms and not all(term in haystack for term in query_terms):
            continue
        rows.append(
            {
                "language": language,
                "locale": locale,
                "stored_locale": stored_locale,
                "ios_lproj": f"{_ios_folder(locale)}.lproj",
                "android_values": _android_values(locale),
                "notes": notes,
            }
        )
    return CommandResult(0, [], payload={"locales": rows, "query": query})


def _ios_folder(locale: str) -> str:
    parts = locale.split("-")
    if len(parts) == 2 and DEFAULT_REGION_BY_LANGUAGE.get(parts[0].lower()) == parts[1].upper():
        return parts[0].lower()
    return locale


def _android_values(locale: str) -> str:
    parts = locale.split("-")
    if len(parts) == 1:
        return f"values-{parts[0].lower()}"
    language = parts[0].lower()
    region = parts[-1]
    if region.isdigit():
        return f"values-b+{language}+{region}"
    if len(region) == 2 and region.isalpha():
        return f"values-{language}-r{region.upper()}"
    return f"values-b+{'+'.join(parts)}"


def _lower_ascii(value: str) -> str:
    return "".join(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in value)
