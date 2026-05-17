from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parley.command_json import CommandJsonAdapter, CommandJsonConfig, CommandJsonError


class CommandJsonAdapterTests(unittest.TestCase):
    def test_invoke_returns_schema_valid_stdout_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(
                tmp,
                """
                import json
                import sys
                request = json.loads(sys.stdin.read())
                print(json.dumps({"ok": True, "request_id": request["request_id"]}))
                """,
            )
            adapter = CommandJsonAdapter(
                CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=5),
                validator=lambda artifact: _require_ok(artifact),
            )

            result = adapter.invoke({"request_id": "req-1"})

            self.assertEqual(result.artifact, {"ok": True, "request_id": "req-1"})
            self.assertEqual(result.telemetry.exit_code, 0)
            self.assertFalse(result.telemetry.timed_out)

    def test_non_zero_exit_is_process_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "import sys\nsys.exit(7)\n")
            adapter = CommandJsonAdapter(CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=5))

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_process_failed")
            self.assertEqual(raised.exception.telemetry.exit_code, 7)

    def test_timeout_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "import time\ntime.sleep(5)\n")
            adapter = CommandJsonAdapter(CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=1))

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_timeout")
            self.assertTrue(raised.exception.telemetry.timed_out)

    def test_non_json_stdout_is_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "print('not-json')\n")
            adapter = CommandJsonAdapter(CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=5))

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_invalid_output")

    def test_non_object_json_stdout_is_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "print('[]')\n")
            adapter = CommandJsonAdapter(CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=5))

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_invalid_output")

    def test_validator_failure_is_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "print('{\"ok\": false}')\n")
            adapter = CommandJsonAdapter(
                CommandJsonConfig(command=sys.executable, args=(str(script),), cwd=Path(tmp), timeout_seconds=5),
                validator=lambda artifact: _require_ok(artifact),
            )

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_invalid_output")

    def test_output_file_transport_uses_request_and_response_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(
                tmp,
                """
                import json
                import os
                request = json.loads(open(os.environ["PARLEY_REQUEST_PATH"], encoding="utf-8").read())
                with open(os.environ["PARLEY_RESPONSE_PATH"], "w", encoding="utf-8") as output:
                    json.dump({"ok": True, "request_id": request["request_id"]}, output)
                """,
            )
            adapter = CommandJsonAdapter(
                CommandJsonConfig(
                    command=sys.executable,
                    args=(str(script),),
                    cwd=Path(tmp),
                    timeout_seconds=5,
                    request_delivery="output_file",
                    response_mode="output_file_json",
                ),
                validator=lambda artifact: _require_ok(artifact),
            )

            result = adapter.invoke({"request_id": "req-1"})

            self.assertEqual(result.artifact, {"ok": True, "request_id": "req-1"})
            self.assertEqual(list((Path(tmp) / ".parley/provider-io").glob("*.json")), [])

    def test_output_file_missing_response_is_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "pass\n")
            adapter = CommandJsonAdapter(
                CommandJsonConfig(
                    command=sys.executable,
                    args=(str(script),),
                    cwd=Path(tmp),
                    timeout_seconds=5,
                    request_delivery="output_file",
                    response_mode="output_file_json",
                )
            )

            with self.assertRaises(CommandJsonError) as raised:
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(raised.exception.classification, "provider_invalid_output")

    def test_output_file_transport_cleans_up_after_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, "import sys\nsys.exit(9)\n")
            adapter = CommandJsonAdapter(
                CommandJsonConfig(
                    command=sys.executable,
                    args=(str(script),),
                    cwd=Path(tmp),
                    timeout_seconds=5,
                    request_delivery="output_file",
                    response_mode="output_file_json",
                )
            )

            with self.assertRaises(CommandJsonError):
                adapter.invoke({"request_id": "req-1"})

            self.assertEqual(list((Path(tmp) / ".parley/provider-io").glob("*.json")), [])

    def test_stdout_json_envelope_unwraps_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(tmp, 'print(\'{"structured_output": {"ok": true}}\')\n')
            adapter = CommandJsonAdapter(
                CommandJsonConfig(
                    command=sys.executable,
                    args=(str(script),),
                    cwd=Path(tmp),
                    timeout_seconds=5,
                    response_mode="stdout_json_envelope",
                )
            )

            result = adapter.invoke({"request_id": "req-1"})

            self.assertEqual(result.artifact, {"ok": True})

    def test_stdout_json_envelope_unwraps_result_json_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = _script(
                tmp,
                """
                import json
                print(json.dumps({"result": json.dumps({"ok": True})}))
                """,
            )
            adapter = CommandJsonAdapter(
                CommandJsonConfig(
                    command=sys.executable,
                    args=(str(script),),
                    cwd=Path(tmp),
                    timeout_seconds=5,
                    response_mode="stdout_json_envelope",
                )
            )

            result = adapter.invoke({"request_id": "req-1"})

            self.assertEqual(result.artifact, {"ok": True})


def _script(root: str, source: str) -> Path:
    path = Path(root) / "fake_provider.py"
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return path


def _require_ok(artifact: dict) -> None:
    if artifact.get("ok") is not True:
        raise ValueError("expected ok=true")


if __name__ == "__main__":
    unittest.main()
