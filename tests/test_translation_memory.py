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

    def test_import_lproj_dir_registers_targets_and_imports_partial_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            fr = root / "fr.lproj" / "Localizable.strings"
            fr.parent.mkdir()
            fr.write_text('\ufeff"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n', encoding="utf-8")
            bg = root / "bg.lproj" / "Localizable.strings"
            bg.parent.mkdir()
            bg.write_text('"hello" = "Zdravei %@";\n', encoding="utf-8")

            with stable_run_env("2026-05-16T04:05:00.000000Z", "6" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-lproj-dir",
                        "--project-root",
                        str(root),
                        "--source-root",
                        str(root),
                        "--status",
                        "approved",
                        "--locale-map",
                        "bg=bg-BG",
                    ]
                )

            self.assertEqual(code, 1)
            rows = _tm_rows(root)
            self.assertEqual(len(rows), 3)
            self.assertEqual({row["target_locale"] for row in rows}, {"fr-fr", "bg-bg"})
            self.assertEqual({row["human_status"] for row in rows}, {"approved"})
            self.assertEqual(fr.read_text(encoding="utf-8"), '\ufeff"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n')
            inventory = (root / "inventory.yaml").read_text(encoding="utf-8")
            self.assertIn('locale: "fr-fr"', inventory)
            self.assertIn('locale: "bg-bg"', inventory)
            report = root / "reports" / "translation_memory" / "tm_import_lproj_dir--20260516T040500000000Z-66666666666666666666666666666666.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["discovered_count"], 3)
            self.assertEqual(payload["summary"]["skipped_authoritative_count"], 1)
            self.assertEqual(payload["summary"]["target_count"], 2)
            self.assertEqual(payload["summary"]["registered_count"], 2)
            self.assertEqual(payload["summary"]["imported_count"], 3)
            self.assertTrue(payload["summary"]["inventory_written"])
            self.assertTrue(payload["summary"]["tm_written"])
            self.assertEqual(payload["findings"][0]["code"], "missing_key")
            self.assertEqual(payload["findings"][0]["locale"], "bg-bg")
            by_locale = {item["locale"]: item for item in payload["locale_results"]}
            self.assertEqual(by_locale["fr-fr"]["imported_count"], 2)
            self.assertEqual(by_locale["bg-bg"]["missing_count"], 1)

    def test_import_lproj_dir_dry_run_does_not_register_or_write_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            fr = root / "fr.lproj" / "Localizable.strings"
            fr.parent.mkdir()
            fr.write_text('"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n', encoding="utf-8")
            before_inventory = (root / "inventory.yaml").read_text(encoding="utf-8")

            with stable_run_env("2026-05-16T04:06:00.000000Z", "7" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-lproj-dir",
                        "--project-root",
                        str(root),
                        "--source-root",
                        str(root),
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual((root / "inventory.yaml").read_text(encoding="utf-8"), before_inventory)
            self.assertEqual(_tm_rows(root), [])
            report = root / "reports" / "translation_memory" / "tm_import_lproj_dir--20260516T040600000000Z-77777777777777777777777777777777.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["registered_count"], 1)
            self.assertEqual(payload["summary"]["imported_count"], 2)
            self.assertFalse(payload["summary"]["inventory_written"])
            self.assertFalse(payload["summary"]["tm_written"])
            self.assertTrue(payload["summary"]["dry_run"])

    def test_import_lproj_dir_uses_manifest_localization_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp) / "Localizable strings"
            root = app_root / "parley"
            source = app_root / "en.lproj" / "Localizable.strings"
            source.parent.mkdir(parents=True)
            source.write_text('"hello" = "Hello %@";\n"bye" = "Bye";\n', encoding="utf-8")
            with stable_run_env():
                self.assertEqual(
                    run_cli(
                        [
                            "project",
                            "init",
                            "--project-root",
                            str(root),
                            "--name",
                            "HID Approve",
                            "--authoritative",
                            str(source),
                            "--locale",
                            "en-US",
                        ]
                    ),
                    0,
                )
            target = app_root / "de.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Hallo %@";\n"bye" = "Tschuss";\n', encoding="utf-8")

            with stable_run_env("2026-05-16T04:07:00.000000Z", "a" * 32):
                code = run_cli(
                    [
                        "tm",
                        "import-lproj-dir",
                        "--project-root",
                        str(root),
                        "--source-root",
                        str(app_root),
                    ]
                )

            self.assertEqual(code, 0)
            inventory = (root / "inventory.yaml").read_text(encoding="utf-8")
            self.assertIn('path: "de.lproj/Localizable.strings"', inventory)
            self.assertNotIn('path: "../de.lproj/Localizable.strings"', inventory)
            rows = _tm_rows(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["target_locale"] for row in rows}, {"de-de"})

    def test_import_target_uses_manifest_localization_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp) / "HID Approve"
            root = app_root / "parley"
            source = app_root / "en.lproj" / "Localizable.strings"
            source.parent.mkdir(parents=True)
            source.write_text('"hello" = "Hello %@";\n"bye" = "Bye";\n', encoding="utf-8")
            with stable_run_env():
                self.assertEqual(
                    run_cli(
                        [
                            "project",
                            "init",
                            "--project-root",
                            str(root),
                            "--name",
                            "HID Approve",
                            "--authoritative",
                            str(source),
                            "--locale",
                            "en-US",
                        ]
                    ),
                    0,
                )
            target = app_root / "fr.lproj" / "Localizable.strings"
            target.parent.mkdir()
            target.write_text('"hello" = "Bonjour %@";\n"bye" = "Au revoir";\n', encoding="utf-8")
            with stable_run_env("2026-05-16T04:10:00.000000Z", "9" * 32):
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

            with stable_run_env("2026-05-16T04:11:00.000000Z", "8" * 32):
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
            rows = _tm_rows(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["target_value"] for row in rows}, {"Bonjour %@", "Au revoir"})

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
