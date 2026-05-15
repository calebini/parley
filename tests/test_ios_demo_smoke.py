from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import run_cli, stable_run_env


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


def _finding_codes(payload: dict) -> list[str]:
    return sorted(item["code"] for item in payload["findings"])


if __name__ == "__main__":
    unittest.main()
