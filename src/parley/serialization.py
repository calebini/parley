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

