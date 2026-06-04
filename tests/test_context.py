from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import init_project, run_cli, run_cli_capture, stable_run_env
from parley.serialization import yaml_dump, yaml_load


class ContextValidateTests(unittest.TestCase):
    def test_context_validate_reports_blank_scaffolded_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)

            with stable_run_env("2026-05-17T01:00:00.000000Z", "1" * 32):
                code = run_cli(["context", "validate", "--project-root", str(root)])

            self.assertEqual(code, 1)
            report = root / "reports" / "validation" / "context_validate--20260517T010000000000Z-11111111111111111111111111111111.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["command"], "context_validate")
            self.assertEqual(payload["summary"]["canonical_key_count"], 2)
            self.assertEqual(payload["summary"]["blank_count"], 2)
            self.assertEqual({item["code"] for item in payload["findings"]}, {"context_blank"})
            self.assertFalse(payload["context_complete"])

    def test_context_validate_accepts_populated_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            context = yaml_load((root / "context-anchor.yaml").read_text(encoding="utf-8"))
            context["entries"]["hello"]["context"] = "Greeting on the signed-in home screen."
            context["entries"]["bye"]["context"] = "Short farewell in an account menu."
            (root / "context-anchor.yaml").write_text(yaml_dump(context), encoding="utf-8")

            with stable_run_env("2026-05-17T01:01:00.000000Z", "2" * 32):
                code = run_cli(["context", "validate", "--project-root", str(root)])

            self.assertEqual(code, 0)
            report = root / "reports" / "validation" / "context_validate--20260517T010100000000Z-22222222222222222222222222222222.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["finding_count"], 0)
            self.assertTrue(payload["context_complete"])

    def test_context_validate_reports_missing_anchor_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            (root / "context-anchor.yaml").unlink()

            with stable_run_env("2026-05-17T01:02:00.000000Z", "3" * 32):
                code = run_cli(["context", "validate", "--project-root", str(root)])

            self.assertEqual(code, 1)
            report = root / "reports" / "validation" / "context_validate--20260517T010200000000Z-33333333333333333333333333333333.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["findings"][0]["code"], "context_anchor_missing")

    def test_context_validate_reports_missing_and_stale_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            context = yaml_load((root / "context-anchor.yaml").read_text(encoding="utf-8"))
            del context["entries"]["hello"]
            context["entries"]["bye"]["context"] = "Short farewell in an account menu."
            context["entries"]["old_key"] = {"context": "No longer present in the source file."}
            (root / "context-anchor.yaml").write_text(yaml_dump(context), encoding="utf-8")

            with stable_run_env("2026-05-17T01:03:00.000000Z", "4" * 32):
                code = run_cli(["context", "validate", "--project-root", str(root)])

            self.assertEqual(code, 1)
            report = root / "reports" / "validation" / "context_validate--20260517T010300000000Z-44444444444444444444444444444444.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["missing_count"], 1)
            self.assertEqual(payload["summary"]["stale_count"], 1)
            self.assertEqual(
                {item["code"] for item in payload["findings"]},
                {"context_missing_key", "context_stale_key"},
            )

    def test_context_validate_stale_only_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            context = yaml_load((root / "context-anchor.yaml").read_text(encoding="utf-8"))
            context["entries"]["hello"]["context"] = "Greeting on the signed-in home screen."
            context["entries"]["bye"]["context"] = "Short farewell in an account menu."
            context["entries"]["old_key"] = {"context": "No longer present in the source file."}
            (root / "context-anchor.yaml").write_text(yaml_dump(context), encoding="utf-8")

            with stable_run_env("2026-05-17T01:04:00.000000Z", "5" * 32):
                code = run_cli(["context", "validate", "--project-root", str(root)])

            self.assertEqual(code, 0)
            report = root / "reports" / "validation" / "context_validate--20260517T010400000000Z-55555555555555555555555555555555.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(payload["context_complete"])
            self.assertEqual(payload["findings"][0]["code"], "context_stale_key")
            self.assertEqual(payload["findings"][0]["severity"], "warning")

    def test_context_validate_json_outputs_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)

            with stable_run_env("2026-05-17T01:05:00.000000Z", "6" * 32):
                code, stdout, _ = run_cli_capture(
                    ["--output-format", "json", "context", "validate", "--project-root", str(root)]
                )

            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertFalse(payload["context_complete"])


if __name__ == "__main__":
    unittest.main()
