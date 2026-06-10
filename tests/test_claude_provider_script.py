from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "claude_parley_provider.py"


class ClaudeParleyProviderScriptTests(unittest.TestCase):
    def test_claude_provider_unwraps_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_claude = _fake_claude(Path(tmp), mode="structured_output")
            argv_log = Path(tmp) / "argv.json"

            completed = _run_provider(fake_claude, argv_log)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact = json.loads(completed.stdout)
            self.assertEqual(artifact["schema_version"], "1.0")
            self.assertEqual(artifact["request_id"], "req-1")
            self.assertEqual(artifact["provider_id"], "command-json")
            self.assertEqual(artifact["entries"][0]["translated_text"], "[fr-fr] Hello %@")

            argv = json.loads(argv_log.read_text(encoding="utf-8"))
            self.assertIn("--print", argv)
            self.assertIn("--output-format", argv)
            self.assertIn("json", argv)
            self.assertIn("--no-session-persistence", argv)
            self.assertIn("--permission-mode", argv)
            self.assertIn("dontAsk", argv)
            self.assertIn("--tools", argv)
            self.assertIn("", argv)
            self.assertIn("--json-schema", argv)

    def test_claude_provider_unwraps_result_json_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_claude = _fake_claude(Path(tmp), mode="result_string")
            argv_log = Path(tmp) / "argv.json"

            completed = _run_provider(fake_claude, argv_log)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact = json.loads(completed.stdout)
            self.assertEqual(artifact["entries"][0]["translated_text"], "[fr-fr] Hello %@")

    def test_claude_provider_unwraps_event_array_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_claude = _fake_claude(Path(tmp), mode="event_array")
            argv_log = Path(tmp) / "argv.json"

            completed = _run_provider(fake_claude, argv_log)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact = json.loads(completed.stdout)
            self.assertEqual(artifact["entries"][0]["translated_text"], "[fr-fr] Hello %@")


def _run_provider(fake_claude: Path, argv_log: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PARLEY_CLAUDE_COMMAND"] = str(fake_claude)
    env["PARLEY_CLAUDE_TIMEOUT_SECONDS"] = "5"
    env["FAKE_CLAUDE_ARGV_LOG"] = str(argv_log)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(_request()),
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env=env,
        timeout=10,
    )


def _request() -> dict:
    return {
        "schema_version": "1.0",
        "request_id": "req-1",
        "operation": "translate_batch",
        "provider_id": "command-json",
        "source_locale": "en-us",
        "target_locale": "fr-fr",
        "project_context": {"description": "Authenticator app"},
        "entries": [
            {
                "key": "hello",
                "source_locale": "en-us",
                "target_locale": "fr-fr",
                "source_text": "Hello %@",
                "protected_text": "Hello %@",
                "placeholder_tokens": [{"token": "%@", "kind": "ios_object"}],
                "context_description": "Greeting",
                "glossary_constraints": [],
                "translation_memory_candidates": [],
            }
        ],
    }


def _fake_claude(root: Path, *, mode: str) -> Path:
    path = root / "fake_claude"
    path.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            f"""
            import json
            import os
            from pathlib import Path
            import sys

            Path(os.environ["FAKE_CLAUDE_ARGV_LOG"]).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
            schema = json.loads(sys.argv[sys.argv.index("--json-schema") + 1])
            if "entries" not in schema.get("properties", {{}}):
                raise SystemExit(2)
            prompt = sys.stdin.read()
            marker = "Parley provider request JSON:\\n"
            request = json.loads(prompt.split(marker, 1)[1])
            entry = request["entries"][0]
            response = {{
                "schema_version": "1.0",
                "request_id": request["request_id"],
                "provider_id": request["provider_id"],
                "status": "ok",
                "entries": [
                    {{
                        "key": entry["key"],
                        "status": "translated",
                        "translated_text": f"[{{entry['target_locale']}}] {{entry['source_text']}}",
                        "failure_reason": None,
                    }}
                ],
                "provider_metadata": None,
            }}
            if {mode!r} == "structured_output":
                print(json.dumps({{"structured_output": response}}))
            elif {mode!r} == "result_string":
                print(json.dumps({{"result": json.dumps(response)}}))
            else:
                print(json.dumps([{{"type": "result", "structured_output": response}}]))
            """
        ).lstrip(),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | 0o111)
    return path


if __name__ == "__main__":
    unittest.main()
