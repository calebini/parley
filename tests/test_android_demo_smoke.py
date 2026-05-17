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


class AndroidDemoSmokeTests(unittest.TestCase):
    def test_android_demo_exercises_translate_validate_and_tm_reuse(self) -> None:
        fixture = ROOT / "examples" / "android-demo"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "android-demo"
            shutil.copytree(fixture, root)

            source = root / "values" / "strings.xml"
            target = root / "values-fr" / "strings.xml"

            with stable_run_env("2026-05-17T09:00:00.000000Z", "1" * 32):
                init_code = run_cli(
                    [
                        "project",
                        "init",
                        "--project-root",
                        str(root),
                        "--name",
                        "Pocket Tasks Android",
                        "--authoritative",
                        str(source),
                        "--locale",
                        "en-US",
                    ]
                )
            self.assertEqual(init_code, 0)

            with stable_run_env("2026-05-17T09:00:30.000000Z", "2" * 32):
                seed_code = run_cli(["context", "seed", "--project-root", str(root)])
            self.assertEqual(seed_code, 0)

            with stable_run_env("2026-05-17T09:01:00.000000Z", "3" * 32):
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

            with stable_run_env("2026-05-17T09:02:00.000000Z", "4" * 32):
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
            translated = target.read_text(encoding="utf-8")
            self.assertIn('<string name="home_greeting">[fr-fr] Hello, %1$s</string>', translated)
            self.assertIn('<string name="task_count">[fr-fr] %d tasks due today</string>', translated)
            self.assertIn('<string name="sync_status">[fr-fr] Last synced {time}</string>', translated)
            self.assertIn("Upgrade &amp; keep planning", translated)

            translate_report = (
                root
                / "reports"
                / "translation"
                / "translate--20260517T090200000000Z-44444444444444444444444444444444.json"
            )
            translate_payload = json.loads(translate_report.read_text(encoding="utf-8"))
            self.assertEqual(translate_payload["summary"]["generated_count"], 6)
            self.assertTrue(translate_payload["summary"]["written_target"])
            self.assertTrue(translate_payload["summary"]["tm_written"])
            self.assertEqual(_tm_count(root), 6)

            with stable_run_env("2026-05-17T09:03:00.000000Z", "5" * 32):
                validate_code = run_cli(["validate", "--project-root", str(root), "--no-authoritative"])
            self.assertEqual(validate_code, 0)

            target.write_text("<resources>\n</resources>\n", encoding="utf-8")
            with stable_run_env("2026-05-17T09:04:00.000000Z", "6" * 32):
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
                / "translate--20260517T090400000000Z-66666666666666666666666666666666.json"
            )
            reuse_payload = json.loads(reuse_report.read_text(encoding="utf-8"))
            self.assertEqual(reuse_payload["summary"]["generated_count"], 0)
            self.assertEqual(reuse_payload["summary"]["reused_count"], 6)
            self.assertEqual(reuse_payload["provider_status"], "not_applicable")


def _tm_count(root: Path) -> int:
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        return int(conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
