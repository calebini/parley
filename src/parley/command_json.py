from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
from time import monotonic
from typing import Any, Callable

from parley.serialization import canonical_json_bytes


JsonValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class CommandJsonConfig:
    command: str
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    timeout_seconds: int = 30
    request_delivery: str = "stdin_json"
    response_mode: str = "stdout_json"


@dataclass(frozen=True)
class CommandJsonTelemetry:
    command: str
    started_at: str
    finished_at: str | None
    duration_ms: int
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CommandJsonResult:
    artifact: dict[str, Any]
    telemetry: CommandJsonTelemetry


class CommandJsonError(RuntimeError):
    def __init__(self, classification: str, message: str, telemetry: CommandJsonTelemetry | None = None) -> None:
        super().__init__(message)
        self.classification = classification
        self.telemetry = telemetry


class CommandJsonAdapter:
    def __init__(self, config: CommandJsonConfig, validator: JsonValidator | None = None) -> None:
        self.config = config
        self.validator = validator

    def invoke(self, request: dict[str, Any]) -> CommandJsonResult:
        self._validate_config()
        cwd = self._resolved_cwd()
        started_at = _now()
        started_monotonic = monotonic()
        payload = canonical_json_bytes(request) + b"\n"
        args = [self.config.command, *self.config.args]
        if self.config.request_delivery != "stdin_json":
            raise CommandJsonError("invalid_configuration", "only stdin_json request delivery is implemented")
        if self.config.response_mode != "stdout_json":
            raise CommandJsonError("invalid_configuration", "only stdout_json response mode is implemented")
        try:
            completed = _run_process(
                args,
                cwd=cwd,
                input_bytes=payload,
                timeout_seconds=self.config.timeout_seconds,
            )
        except FileNotFoundError as exc:
            telemetry = _telemetry(
                command=self.config.command,
                started_at=started_at,
                started_monotonic=started_monotonic,
                exit_code=None,
                timed_out=False,
                stdout=b"",
                stderr=str(exc).encode("utf-8"),
            )
            raise CommandJsonError("provider_unavailable", f"provider command not found: {self.config.command}", telemetry) from exc
        except PermissionError as exc:
            telemetry = _telemetry(
                command=self.config.command,
                started_at=started_at,
                started_monotonic=started_monotonic,
                exit_code=None,
                timed_out=False,
                stdout=b"",
                stderr=str(exc).encode("utf-8"),
            )
            raise CommandJsonError("provider_unavailable", f"provider command not executable: {self.config.command}", telemetry) from exc
        except subprocess.TimeoutExpired as exc:
            telemetry = _telemetry(
                command=self.config.command,
                started_at=started_at,
                started_monotonic=started_monotonic,
                exit_code=None,
                timed_out=True,
                stdout=_bytes_or_empty(exc.output),
                stderr=_bytes_or_empty(exc.stderr),
            )
            raise CommandJsonError("provider_timeout", f"provider command timed out after {self.config.timeout_seconds} seconds", telemetry) from exc
        telemetry = _telemetry(
            command=self.config.command,
            started_at=started_at,
            started_monotonic=started_monotonic,
            exit_code=completed.returncode,
            timed_out=False,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if completed.returncode != 0:
            raise CommandJsonError("provider_process_failed", f"provider command exited {completed.returncode}", telemetry)
        artifact = _parse_stdout_json(completed.stdout, telemetry)
        if self.validator is not None:
            try:
                self.validator(artifact)
            except ValueError as exc:
                raise CommandJsonError("provider_invalid_output", str(exc), telemetry) from exc
        return CommandJsonResult(artifact=artifact, telemetry=telemetry)

    def _validate_config(self) -> None:
        if not isinstance(self.config.timeout_seconds, int) or self.config.timeout_seconds <= 0:
            raise CommandJsonError("invalid_configuration", "timeout_seconds must be a positive integer")
        if self.config.request_delivery != "stdin_json":
            raise CommandJsonError("invalid_configuration", "unsupported request_delivery")
        if self.config.response_mode != "stdout_json":
            raise CommandJsonError("invalid_configuration", "unsupported response_mode")

    def _resolved_cwd(self) -> Path | None:
        if self.config.cwd is None:
            return None
        cwd = self.config.cwd.resolve()
        if not cwd.is_dir():
            raise CommandJsonError("invalid_configuration", f"provider cwd is not a directory: {cwd}")
        return cwd


def _run_process(
    args: list[str],
    *,
    cwd: Path | None,
    input_bytes: bytes,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[bytes]:
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(input=input_bytes, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(args, timeout_seconds, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError:
            process.kill()


def _parse_stdout_json(stdout: bytes, telemetry: CommandJsonTelemetry) -> dict[str, Any]:
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CommandJsonError("provider_invalid_output", "provider stdout is not valid UTF-8", telemetry) from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CommandJsonError("provider_invalid_output", "provider stdout is not JSON", telemetry) from exc
    if not isinstance(value, dict):
        raise CommandJsonError("provider_invalid_output", "provider stdout JSON is not an object", telemetry)
    return value


def _telemetry(
    *,
    command: str,
    started_at: str,
    started_monotonic: float,
    exit_code: int | None,
    timed_out: bool,
    stdout: bytes,
    stderr: bytes,
) -> CommandJsonTelemetry:
    return CommandJsonTelemetry(
        command=command,
        started_at=started_at,
        finished_at=None if timed_out else _now(),
        duration_ms=max(0, int((monotonic() - started_monotonic) * 1000)),
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=_decode_lossy(stdout),
        stderr=_decode_lossy(stderr),
    )


def _decode_lossy(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _bytes_or_empty(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
