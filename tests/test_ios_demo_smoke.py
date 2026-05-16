from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import run_cli, stable_run_env
from parley.serialization import yaml_dump


class IosDemoSmokeTests(unittest.TestCase):
    def test_ios_demo_fixture_exercises_clean_and_broken_localizations(self) -> None:
        fixture = ROOT / "examples" / "ios-demo"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ios-demo"
            shutil.copytree(fixture, root)

            source = root / "en.lproj" / "Localizable.strings"
            clean = root / "fr-clean.lproj" / "Localizable.strings"
            broken = root / "fr-broken.lproj" / "Localizable.strings"

            with stable_run_env("2026-05-15T10:00:00.000000Z", "1" * 32):
                init_code = run_cli(
                    [
                        "project",
                        "init",
                        "--project-root",
                        str(root),
                        "--name",
                        "Pocket Tasks",
                        "--authoritative",
                        str(source),
                        "--locale",
                        "en-US",
                    ]
                )
            self.assertEqual(init_code, 0)

            with stable_run_env("2026-05-15T10:01:00.000000Z", "2" * 32):
                clean_code = run_cli(
                    [
                        "localization",
                        "add",
                        str(clean),
                        "--project-root",
                        str(root),
                        "--locale",
                        "fr-FR",
                    ]
                )
            self.assertEqual(clean_code, 0)

            with stable_run_env("2026-05-15T10:02:00.000000Z", "3" * 32):
                broken_code = run_cli(
                    [
                        "localization",
                        "add",
                        str(broken),
                        "--project-root",
                        str(root),
                        "--locale",
                        "fr-FR",
                    ]
                )
            self.assertEqual(broken_code, 1)

            broken_report = (
                root
                / "reports"
                / "validation"
                / "localization_add--20260515T100200000000Z-33333333333333333333333333333333.json"
            )
            broken_payload = json.loads(broken_report.read_text(encoding="utf-8"))
            self.assertEqual(
                _finding_codes(broken_payload),
                ["extra_key", "missing_key", "placeholder_mismatch", "placeholder_mismatch"],
            )

            with stable_run_env("2026-05-15T10:03:00.000000Z", "4" * 32):
                validate_code = run_cli(["validate", "--project-root", str(root), "--no-authoritative"])
            self.assertEqual(validate_code, 1)

            validate_report = (
                root
                / "reports"
                / "validation"
                / "validate--20260515T100300000000Z-44444444444444444444444444444444.json"
            )
            validate_payload = json.loads(validate_report.read_text(encoding="utf-8"))
            self.assertEqual(_finding_codes(validate_payload), _finding_codes(broken_payload))

    def test_ios_demo_fixture_exercises_translate_validate_and_tm_reuse(self) -> None:
        fixture = ROOT / "examples" / "ios-demo"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ios-demo"
            shutil.copytree(fixture, root)

            source = root / "en.lproj" / "Localizable.strings"
            target = root / "fr-generated.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text("", encoding="utf-8")

            with stable_run_env("2026-05-15T11:00:00.000000Z", "5" * 32):
                init_code = run_cli(
                    [
                        "project",
                        "init",
                        "--project-root",
                        str(root),
                        "--name",
                        "Pocket Tasks",
                        "--authoritative",
                        str(source),
                        "--locale",
                        "en-US",
                    ]
                )
            self.assertEqual(init_code, 0)
            _populate_context_anchor(root)

            with stable_run_env("2026-05-15T11:01:00.000000Z", "6" * 32):
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

            with stable_run_env("2026-05-15T11:02:00.000000Z", "7" * 32):
                translate_code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--provider",
                        "dummy",
                    ]
                )
            self.assertEqual(translate_code, 0)
            translated_text = target.read_text(encoding="utf-8")
            self.assertIn('"home.greeting" = "[fr-fr] Hello, %@";', translated_text)
            self.assertIn('"task.count" = "[fr-fr] %d tasks due today";', translated_text)

            translate_report = (
                root
                / "reports"
                / "translation"
                / "translate--20260515T110200000000Z-77777777777777777777777777777777.json"
            )
            translate_payload = json.loads(translate_report.read_text(encoding="utf-8"))
            self.assertEqual(translate_payload["provider_status"], "used")
            self.assertEqual(_outcomes(translate_payload), {"generated"})
            self.assertEqual(translate_payload["summary"]["generated_count"], 8)
            self.assertEqual(_tm_count(root), 8)

            with stable_run_env("2026-05-15T11:03:00.000000Z", "8" * 32):
                validate_code = run_cli(["validate", "--project-root", str(root), "--no-authoritative"])
            self.assertEqual(validate_code, 0)

            target.write_text("", encoding="utf-8")
            with stable_run_env("2026-05-15T11:04:00.000000Z", "9" * 32):
                reuse_code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "tm_only",
                    ]
                )
            self.assertEqual(reuse_code, 0)

            reuse_report = (
                root
                / "reports"
                / "translation"
                / "translate--20260515T110400000000Z-99999999999999999999999999999999.json"
            )
            reuse_payload = json.loads(reuse_report.read_text(encoding="utf-8"))
            self.assertEqual(reuse_payload["provider_status"], "not_applicable")
            self.assertEqual(_outcomes(reuse_payload), {"reused"})
            self.assertEqual(reuse_payload["summary"]["reused_count"], 8)


def _finding_codes(payload: dict) -> list[str]:
    return sorted(item["code"] for item in payload["findings"])


def _outcomes(payload: dict) -> set[str]:
    return {item["outcome"] for item in payload["per_key_outcomes"]}


def _populate_context_anchor(root: Path) -> None:
    canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
    anchor = {
        "schema_version": "1.0",
        "project_id": canonical["project_id"],
        "authoritative_locale": canonical["authoritative_locale"],
        "project_context": {"description": "Synthetic iOS demo app."},
        "entries": {
            key: {"context": f"Demo UI copy for {key}"}
            for key in sorted(canonical["entries"])
        },
    }
    (root / "context-anchor.yaml").write_text(yaml_dump(anchor), encoding="utf-8")


def _tm_count(root: Path) -> int:
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        return int(conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
