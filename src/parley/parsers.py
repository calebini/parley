from __future__ import annotations

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from parley.errors import ParserError
from parley.hashing import sha256_canonical_json


@dataclass(frozen=True)
class ParsedEntry:
    key: str
    value: str
    placeholders: list[dict[str, str]]

    @property
    def placeholder_signature(self) -> str:
        if not self.placeholders:
            return ""
        return "|".join(item["token"] for item in self.placeholders)


@dataclass(frozen=True)
class ParsedLocalization:
    entries: list[ParsedEntry]
    normalized_hash: str


_IOS_PAIR_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;\s*$')
_PRINTF_PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[@dfius]")
_BRACE_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def infer_format(path: str) -> str | None:
    lower = path.lower()
    if lower.endswith(".strings"):
        return "ios_strings"
    if lower.endswith(".xml"):
        return "android_xml"
    return None


def parse_localization(content: str, fmt: str) -> ParsedLocalization:
    if fmt == "ios_strings":
        entries = _parse_ios_strings(content)
    elif fmt == "android_xml":
        entries = _parse_android_xml(content)
    else:
        raise ParserError(f"unsupported localization format: {fmt}")
    normalized = [
        {"key": entry.key, "value": entry.value, "placeholder_signature": entry.placeholder_signature}
        for entry in sorted(entries, key=lambda item: item.key)
    ]
    return ParsedLocalization(entries=sorted(entries, key=lambda item: item.key), normalized_hash=sha256_canonical_json(normalized))


def _parse_ios_strings(content: str) -> list[ParsedEntry]:
    entries: list[ParsedEntry] = []
    in_block_comment = False
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        match = _IOS_PAIR_RE.match(line)
        if not match:
            raise ParserError(f"invalid ios_strings entry at line {line_number}")
        key = _decode_quoted(match.group(1), line_number)
        value = _decode_quoted(match.group(2), line_number)
        entries.append(ParsedEntry(key=key, value=value, placeholders=_extract_placeholders(value)))
    return _ensure_unique(entries)


def _parse_android_xml(content: str) -> list[ParsedEntry]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ParserError(f"invalid android_xml: {exc}") from exc
    if root.tag != "resources":
        raise ParserError("android_xml root must be <resources>")
    entries: list[ParsedEntry] = []
    for child in root:
        if child.tag != "string":
            continue
        key = child.attrib.get("name")
        if not key:
            raise ParserError("android_xml <string> is missing name")
        value = "".join(child.itertext())
        entries.append(ParsedEntry(key=key, value=value, placeholders=_extract_placeholders(value)))
    return _ensure_unique(entries)


def _decode_quoted(value: str, line_number: int) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError as exc:
        raise ParserError(f"invalid string escape at line {line_number}") from exc


def _extract_placeholders(value: str) -> list[dict[str, str]]:
    tokens = []
    for match in _PRINTF_PLACEHOLDER_RE.finditer(value):
        tokens.append((match.start(), match.group(0)))
    for match in _BRACE_PLACEHOLDER_RE.finditer(value):
        tokens.append((match.start(), match.group(0)))
    return [
        {"token": token, "kind": "placeholder"}
        for _, token in sorted(tokens, key=lambda item: (item[0], item[1]))
    ]


def _ensure_unique(entries: list[ParsedEntry]) -> list[ParsedEntry]:
    seen: set[str] = set()
    for entry in entries:
        if entry.key in seen:
            raise ParserError(f"duplicate localization key: {entry.key}")
        seen.add(entry.key)
    return entries

