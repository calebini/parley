from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from parley.cli import main


def stable_run_env(started_at: str = "2026-05-15T00:00:00.000001Z", nonce: str = "a" * 32):
    return mock.patch.dict(
        "os.environ",
        {"PARLEY_STARTED_AT": started_at, "PARLEY_PROCESS_NONCE_HEX": nonce},
    )


def run_cli(argv: list[str]) -> int:
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return main(argv)


def run_cli_capture(argv: list[str]) -> tuple[int, str, str]:
    out = StringIO()
    err = StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def init_project(root: Path, source_text: str = '"hello" = "Hello %@";\n"bye" = "Bye";\n') -> None:
    source = root / "en.lproj" / "Localizable.strings"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    with stable_run_env():
        code = run_cli(
            [
                "project",
                "init",
                "--project-root",
                str(root),
                "--name",
                "My App",
                "--authoritative",
                str(source),
                "--locale",
                "en-US",
            ]
        )
    if code != 0:
        raise AssertionError(f"project init failed with {code}")

