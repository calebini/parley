from __future__ import annotations

from dataclasses import dataclass


EXIT_OK = 0
EXIT_BLOCKING_FINDINGS = 1
EXIT_USAGE_OR_SCHEMA = 2
EXIT_IO_OR_PARSER = 3
EXIT_PROVIDER = 4


@dataclass(frozen=True)
class ParleyError(Exception):
    message: str
    exit_code: int = EXIT_USAGE_OR_SCHEMA
    failure_category: str = "precondition_failed"

    def __str__(self) -> str:
        return self.message


class UsageError(ParleyError):
    def __init__(self, message: str, *, failure_category: str = "precondition_failed") -> None:
        super().__init__(message, EXIT_USAGE_OR_SCHEMA, failure_category)


class ParserError(ParleyError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_IO_OR_PARSER, "parser")


class FileIOError(ParleyError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_IO_OR_PARSER, "io")

