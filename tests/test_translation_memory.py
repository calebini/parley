from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import init_project, run_cli, stable_run_env


class TranslationMemoryImportTests(unittest.TestCase):
    def test_import_target_imports_clean_existing_localization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = _add_target(root, '"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n')

            with stable_run_env("2026-05-16T04:00:00.000000Z", "1" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-target",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--status",
                        "approved",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), '"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n')
            rows = _tm_rows(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["key"] for row in rows}, {"hello", "bye"})
            self.assertEqual({row["provenance"] for row in rows}, {"imported"})
            self.assertEqual({row["human_status"] for row in rows}, {"approved"})
            self.assertEqual({row["is_current"] for row in rows}, {1})
            report = root / "reports" / "translation_memory" / "tm_import_target--20260516T040000000000Z-11111111111111111111111111111111.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["imported_count"], 2)
            self.assertTrue(payload["summary"]["tm_written"])
            self.assertEqual(payload["findings"], [])

    def test_import_target_imports_valid_entries_while_reporting_missing_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _add_target(root, '"hello" = "Bonjour %@";\n')

            with stable_run_env("2026-05-16T05:00:00.000000Z", "2" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-target",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                    ]
                )

            self.assertEqual(code, 1)
            rows = _tm_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["key"], "hello")
            report = root / "reports" / "translation_memory" / "tm_import_target--20260516T050000000000Z-22222222222222222222222222222222.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["imported_count"], 1)
            self.assertEqual(payload["summary"]["finding_count"], 1)
            self.assertEqual(payload["findings"][0]["code"], "missing_key")
            self.assertEqual(payload["findings"][0]["key"], "bye")

    def test_import_target_dry_run_writes_report_without_memory_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _add_target(root, '"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n')

            with stable_run_env("2026-05-16T06:00:00.000000Z", "3" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-target",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(_tm_rows(root), [])
            report = root / "reports" / "translation_memory" / "tm_import_target--20260516T060000000000Z-33333333333333333333333333333333.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["imported_count"], 2)
            self.assertFalse(payload["summary"]["tm_written"])
            self.assertTrue(payload["summary"]["dry_run"])

    def test_imported_target_memory_can_refill_target_with_tm_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            target = _add_target(root, '"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n')

            with stable_run_env("2026-05-16T07:00:00.000000Z", "4" * 32):
                import_code = run_cli(
                    [
                        "tm",
                        "import-target",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                    ]
                )
            self.assertEqual(import_code, 0)

            target.write_text("", encoding="utf-8")
            with stable_run_env("2026-05-16T08:00:00.000000Z", "5" * 32):
                translate_code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "tm_only",
                        "--no-context",
                    ]
                )

            self.assertEqual(translate_code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), '"bye" = "Au revoir";\n"hello" = "Bonjour %@";\n')
            report = root / "reports" / "translation" / "translate--20260516T080000000000Z-55555555555555555555555555555555.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["reused_count"], 2)
            self.assertEqual({item["outcome"] for item in payload["per_key_outcomes"]}, {"reused"})


def _add_target(root: Path, content: str) -> Path:
    target = root / "fr.lproj" / "Localizable.strings"
    target.parent.mkdir()
    target.write_text(content, encoding="utf-8")
    with stable_run_env("2026-05-16T03:00:00.000000Z", "0" * 32):
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
    if code not in {0, 1}:
        raise AssertionError(f"localization add failed with {code}")
    return target


def _tm_rows(root: Path) -> list[dict]:
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute("SELECT * FROM memory_entries ORDER BY key")]


if __name__ == "__main__":
    unittest.main()
