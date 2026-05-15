from __future__ import annotations

import json
from typing import Any


def without_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [without_nulls(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        without_nulls(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(without_nulls(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def yaml_dump(value: Any) -> str:
    lines: list[str] = []
    _write_yaml(value, lines, 0)
    return "\n".join(lines) + "\n"


def _write_yaml(value: Any, lines: list[str], indent: int) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        for key in sorted(value):
            item = value[key]
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                _write_yaml(item, lines, indent + 2)
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
        return
    if isinstance(value, list):
        if not value:
            lines.append(f"{prefix}[]")
            return
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                _write_yaml(item, lines, indent + 2)
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                _write_yaml(item, lines, indent + 2)
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return
    lines.append(f"{prefix}{_yaml_scalar(value)}")


def _yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_load(text: str) -> Any:
    """Parse the small YAML subset emitted by Parley's deterministic writer."""
    lines = [
        (len(line) - len(line.lstrip(" ")), line.strip())
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return {}
    value, next_index = _parse_yaml_block(lines, 0, lines[0][0])
    if next_index != len(lines):
        raise ValueError("invalid YAML structure")
    return value


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent != indent:
        raise ValueError("invalid YAML indentation")
    if content.startswith("-") or content == "[]":
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_dict(lines, index, indent)


def _parse_yaml_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError("unexpected nested YAML content")
        if ":" not in content or content.startswith("-"):
            raise ValueError("expected YAML mapping")
        key, raw_value = content.split(":", 1)
        raw_value = raw_value.strip()
        if raw_value:
            result[key] = _parse_yaml_scalar(raw_value)
            index += 1
            continue
        if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
            result[key] = {}
            index += 1
            continue
        value, index = _parse_yaml_block(lines, index + 1, lines[index + 1][0])
        result[key] = value
    return result, index


def _parse_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    if lines[index] == (indent, "[]"):
        return [], index + 1
    result: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError("unexpected nested YAML list content")
        if not content.startswith("-"):
            break
        raw_value = content[1:].strip()
        if raw_value:
            result.append(_parse_yaml_scalar(raw_value))
            index += 1
            continue
        if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
            result.append({})
            index += 1
            continue
        value, index = _parse_yaml_block(lines, index + 1, lines[index + 1][0])
        result.append(value)
    return result, index


def _parse_yaml_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if value.startswith('"') and value.endswith('"'):
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    try:
        return int(value)
    except ValueError:
        return value
