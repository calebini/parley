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


class ValidationAndLocalizationTests(unittest.TestCase):
    def test_project_inspect_json_reports_artifact_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            code, stdout, _ = run_cli_capture(
                ["--output-format", "json", "project", "inspect", "--project-root", str(root)]
            )
            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            statuses = {item["artifact"]: item["status"] for item in payload["artifacts"]}
            self.assertEqual(statuses["parley.yaml"], "present")
            self.assertEqual(statuses["translation-memory.sqlite"], "present")

    def test_validate_clean_project_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            with stable_run_env("2026-05-15T02:00:00.000000Z", "c" * 32):
                code = run_cli(["validate", "--project-root", str(root)])
            self.assertEqual(code, 0)
            report = root / "reports" / "validation" / "validate--20260515T020000000000Z-cccccccccccccccccccccccccccccccc.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["command"], "validate")
            self.assertEqual(payload["findings"], [])
            self.assertEqual(payload["validated_localizations"][0]["status"], "validated")

    def test_validate_target_placeholder_mismatch_exits_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = root / "fr.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Bonjour";\n"bye" = "Au revoir";\n', encoding="utf-8")
            with stable_run_env("2026-05-15T03:00:00.000000Z", "d" * 32):
                add_code = run_cli(
                    [
                        "localization",
                        "add",
                        str(target),
                        "--project-root",
                        str(root),
                        "--locale",
                        "fr-FR",
                    ]
                )
            self.assertEqual(add_code, 1)
            with stable_run_env("2026-05-15T04:00:00.000000Z", "e" * 32):
                validate_code = run_cli(["validate", "--project-root", str(root), "--no-authoritative"])
            self.assertEqual(validate_code, 1)
            report = root / "reports" / "validation" / "validate--20260515T040000000000Z-eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(any(item["code"] == "placeholder_mismatch" for item in payload["findings"]))

    def test_localization_add_target_updates_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = root / "fr.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n', encoding="utf-8")
            with stable_run_env("2026-05-15T05:00:00.000000Z", "f" * 32):
                code = run_cli(
                    [
                        "localization",
                        "add",
                        str(target),
                        "--project-root",
                        str(root),
                        "--locale",
                        "fr-FR",
                    ]
                )
            self.assertEqual(code, 0)
            inventory_text = (root / "inventory.yaml").read_text(encoding="utf-8")
            self.assertIn('locale: "fr-fr"', inventory_text)
            self.assertIn('role: "target"', inventory_text)
            report = root / "reports" / "validation" / "localization_add--20260515T050000000000Z-ffffffffffffffffffffffffffffffff.json"
            self.assertTrue(report.exists())

    def test_validate_missing_inventory_writes_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            (root / "inventory.yaml").unlink()
            before = sorted((root / "reports" / "validation").iterdir())
            with stable_run_env("2026-05-15T06:00:00.000000Z", "1" * 32):
                code = run_cli(["validate", "--project-root", str(root)])
            after = sorted((root / "reports" / "validation").iterdir())
            self.assertEqual(code, 2)
            self.assertEqual(before, after)

    def test_localization_add_malformed_target_writes_parse_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = root / "fr.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Bonjour"\n', encoding="utf-8")

            with stable_run_env("2026-05-15T07:00:00.000000Z", "2" * 32):
                code = run_cli(
                    [
                        "localization",
                        "add",
                        str(target),
                        "--project-root",
                        str(root),
                        "--locale",
                        "fr-FR",
                    ]
                )

            self.assertEqual(code, 3)
            report = root / "reports" / "validation" / "localization_add--20260515T070000000000Z-22222222222222222222222222222222.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure_category"], "precondition_failed")
            self.assertEqual(payload["findings"][0]["code"], "parse_error")
            self.assertEqual(payload["findings"][0]["failure_category"], "parser")

    def test_validate_malformed_target_writes_parse_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = root / "fr.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n', encoding="utf-8")
            with stable_run_env("2026-05-15T08:00:00.000000Z", "3" * 32):
                self.assertEqual(
                    run_cli(
                        [
                            "localization",
                            "add",
                            str(target),
                            "--project-root",
                            str(root),
                            "--locale",
                            "fr-FR",
                        ]
                    ),
                    0,
                )
            target.write_text('"hello" = "Bonjour %@";\n"bye" = "Au revoir"\n', encoding="utf-8")

            with stable_run_env("2026-05-15T09:00:00.000000Z", "4" * 32):
                code = run_cli(["validate", "--project-root", str(root), "--no-authoritative"])

            self.assertEqual(code, 3)
            report = root / "reports" / "validation" / "validate--20260515T090000000000Z-44444444444444444444444444444444.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure_category"], "parse_error")
            self.assertEqual(payload["validated_localizations"][0]["status"], "parse_error")
            self.assertEqual(payload["findings"][0]["code"], "parse_error")


if __name__ == "__main__":
    unittest.main()
