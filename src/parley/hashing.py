from __future__ import annotations

import hashlib
from typing import Any

from parley.serialization import canonical_json_bytes


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_canonical_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()

