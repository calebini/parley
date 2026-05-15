from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parley.cli import main
from helpers import run_cli, stable_run_env


class ProjectInitTests(unittest.TestCase):
    def test_help_runs(self) -> None:
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_project_init_creates_mvp_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "en.lproj" / "Localizable.strings"
            source.parent.mkdir()
            source.write_text('"hello" = "Hello %@";\n"bye" = "Bye";\n', encoding="utf-8")
            with stable_run_env():
                exit_code = run_cli(
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
            self.assertEqual(exit_code, 0)
            for rel in [
                "parley.yaml",
                "inventory.yaml",
                "canonical-inventory.json",
                "context-anchor.yaml",
                "glossary.yaml",
                "translation-memory.sqlite",
            ]:
                self.assertTrue((root / rel).exists(), rel)
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(list(canonical["entries"]), ["bye", "hello"])
            self.assertEqual(canonical["authoritative_locale"], "en-us")
            self.assertEqual(canonical["entries"]["hello"]["placeholder_signature"], "%@")
            self.assertTrue((root / "reports" / "validation" / _expected_report_name()).exists())
            with sqlite3.connect(root / "translation-memory.sqlite") as conn:
                schema_version = conn.execute(
                    "SELECT value FROM metadata WHERE key = 'schema_version'"
                ).fetchone()[0]
            self.assertEqual(schema_version, "1.0")

    def test_project_init_without_force_refuses_existing_managed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "parley.yaml").write_text("sentinel", encoding="utf-8")
            source = root / "Localizable.strings"
            source.write_text('"hello" = "Hello";\n', encoding="utf-8")
            with stable_run_env():
                exit_code = run_cli(
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
            self.assertEqual(exit_code, 2)
            self.assertEqual((root / "parley.yaml").read_text(encoding="utf-8"), "sentinel")
            self.assertFalse((root / "inventory.yaml").exists())

    def test_project_init_force_replaces_core_but_preserves_reports_and_parley_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Localizable.strings"
            source.write_text('"hello" = "Hello";\n', encoding="utf-8")
            (root / "reports" / "validation").mkdir(parents=True)
            (root / "reports" / "validation" / "old.json").write_text("old", encoding="utf-8")
            (root / ".parley").mkdir()
            (root / ".parley" / "keep.txt").write_text("keep", encoding="utf-8")
            (root / "parley.yaml").write_text("old manifest", encoding="utf-8")
            with stable_run_env("2026-05-15T01:02:03.000004Z", "b" * 32):
                exit_code = run_cli(
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
                        "--force",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn('schema_version: "1.0"', (root / "parley.yaml").read_text(encoding="utf-8"))
            self.assertEqual((root / "reports" / "validation" / "old.json").read_text(encoding="utf-8"), "old")
            self.assertEqual((root / ".parley" / "keep.txt").read_text(encoding="utf-8"), "keep")
            self.assertTrue(
                (root / "reports" / "validation" / "project_init--20260515T010203000004Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.json").exists()
            )

    def test_project_init_rejects_authoritative_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as project_tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(project_tmp)
            outside = Path(outside_tmp) / "Localizable.strings"
            outside.write_text('"hello" = "Hello";\n', encoding="utf-8")
            with stable_run_env():
                exit_code = run_cli(
                    [
                        "project",
                        "init",
                        "--project-root",
                        str(root),
                        "--name",
                        "My App",
                        "--authoritative",
                        str(outside),
                        "--locale",
                        "en-US",
                    ]
                )
            self.assertEqual(exit_code, 2)
            self.assertFalse((root / "parley.yaml").exists())

    def test_project_init_parse_failure_leaves_no_partial_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Localizable.strings"
            source.write_text('"hello" = "Hello"\n', encoding="utf-8")
            with stable_run_env():
                exit_code = run_cli(
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
            self.assertEqual(exit_code, 3)
            for rel in ["parley.yaml", "inventory.yaml", "canonical-inventory.json", "context-anchor.yaml"]:
                self.assertFalse((root / rel).exists(), rel)

    def test_project_init_rolls_back_if_report_path_exists_at_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Localizable.strings"
            source.write_text('"hello" = "Hello";\n', encoding="utf-8")
            report = root / "reports" / "validation" / _expected_report_name()
            original_exists = Path.exists

            def race_exists(path: Path) -> bool:
                if path == report:
                    report.parent.mkdir(parents=True, exist_ok=True)
                    report.write_text("existing", encoding="utf-8")
                    return True
                return original_exists(path)

            with stable_run_env(), mock.patch.object(Path, "exists", race_exists):
                exit_code = run_cli(
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
            self.assertEqual(exit_code, 3)
            self.assertEqual(report.read_text(encoding="utf-8"), "existing")
            self.assertFalse((root / "parley.yaml").exists())
            self.assertFalse((root / "inventory.yaml").exists())


def _expected_report_name() -> str:
    return "project_init--20260515T000000000001Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json"


if __name__ == "__main__":
    unittest.main()
