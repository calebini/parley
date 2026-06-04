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

from helpers import init_project, run_cli, run_cli_capture, stable_run_env
from parley.serialization import yaml_dump, yaml_load


class GlossaryTests(unittest.TestCase):
    def test_glossary_init_creates_skeleton_for_existing_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            (root / "glossary.yaml").unlink()

            with stable_run_env("2026-05-16T02:40:00.000000Z", "4" * 32):
                code = run_cli(["glossary", "init", "--project-root", str(root)])

            self.assertEqual(code, 0)
            glossary = yaml_load((root / "glossary.yaml").read_text(encoding="utf-8"))
            self.assertEqual(
                glossary,
                {
                    "schema_version": "1.0",
                    "project_id": "myapp",
                    "glossary_version": "mvp",
                    "terms": [],
                },
            )
            report = root / "reports" / "glossary" / "glossary_init--20260516T024000000000Z-44444444444444444444444444444444.json"
            self.assertTrue(report.exists())

    def test_glossary_init_with_example_creates_instructional_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            (root / "glossary.yaml").unlink()

            with stable_run_env("2026-05-16T02:45:00.000000Z", "7" * 32):
                code = run_cli(["glossary", "init", "--project-root", str(root), "--with-example"])

            self.assertEqual(code, 0)
            content = (root / "glossary.yaml").read_text(encoding="utf-8")
            self.assertIn('part_of_speech: "Replace with noun, verb, adjective, product_name, acronym, or phrase"', content)
            self.assertIn("fr-fr:", content)
            self.assertIn("de-de:", content)
            glossary = yaml_load(content)
            term = glossary["terms"][0]
            self.assertEqual(term["id"], "replace-with-stable-term-id")
            self.assertEqual(term["targets"]["de-de"]["term"], "Replace with the preferred translation for another locale")
            report = root / "reports" / "glossary" / "glossary_init--20260516T024500000000Z-77777777777777777777777777777777.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(payload["inputs"]["with_example"])
            self.assertEqual(payload["summary"]["term_count"], 1)

    def test_glossary_init_refuses_existing_file_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            before = (root / "glossary.yaml").read_text(encoding="utf-8")

            with stable_run_env("2026-05-16T02:50:00.000000Z", "5" * 32):
                code = run_cli(["glossary", "init", "--project-root", str(root)])

            self.assertEqual(code, 2)
            self.assertEqual((root / "glossary.yaml").read_text(encoding="utf-8"), before)
            self.assertFalse((root / "reports" / "glossary" / "glossary_init--20260516T025000000000Z-55555555555555555555555555555555.json").exists())

    def test_glossary_init_force_replaces_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _write_glossary(root)

            with stable_run_env("2026-05-16T02:55:00.000000Z", "6" * 32):
                code = run_cli(["glossary", "init", "--project-root", str(root), "--force"])

            self.assertEqual(code, 0)
            self.assertEqual(yaml_load((root / "glossary.yaml").read_text(encoding="utf-8"))["terms"], [])

    def test_glossary_import_replace_writes_terms_artifact_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            glossary_file = root / "incoming-glossary.yaml"
            glossary_file.write_text(
                yaml_dump(
                    {
                        "schema_version": "1.0",
                        "project_id": "myapp",
                        "glossary_version": "product-1",
                        "terms": [
                            {
                                "id": "access-token",
                                "source": "Access token",
                                "targets": {"fr-fr": {"term": "jeton d'acces", "status": "approved"}},
                                "forbidden": {"fr-fr": ["token d'acces"]},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with stable_run_env("2026-05-16T03:00:00.000000Z", "1" * 32):
                code = run_cli(
                    [
                        "glossary",
                        "import",
                        "--project-root",
                        str(root),
                        "--file",
                        str(glossary_file),
                    ]
                )

            self.assertEqual(code, 0)
            glossary = yaml_load((root / "glossary.yaml").read_text(encoding="utf-8"))
            self.assertEqual(glossary["terms"][0]["id"], "access-token")
            self.assertNotIn("rules", glossary)
            report = root / "reports" / "glossary" / "glossary_import--20260516T030000000000Z-11111111111111111111111111111111.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["term_count"], 1)
            self.assertTrue(payload["summary"]["glossary_written"])

    def test_glossary_list_filters_by_locale_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _write_glossary(root)

            code, stdout, _ = run_cli_capture(
                ["glossary", "list", "--project-root", str(root), "--locale", "fr-FR", "--query", "access"]
            )

            self.assertEqual(code, 0)
            self.assertIn("access-token", stdout)
            self.assertIn("jeton d'acces", stdout)

    def test_glossary_validate_reports_ambiguous_terms_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            glossary = {
                "schema_version": "1.0",
                "project_id": "myapp",
                "glossary_version": "product-1",
                "terms": [
                    {"id": "one", "source": "Account"},
                    {"id": "two", "source": "Account"},
                ],
            }
            (root / "glossary.yaml").write_text(yaml_dump(glossary), encoding="utf-8")

            with stable_run_env("2026-05-16T03:10:00.000000Z", "2" * 32):
                code = run_cli(["glossary", "validate", "--project-root", str(root)])

            self.assertEqual(code, 0)
            payload = json.loads(
                (root / "reports" / "glossary" / "glossary_validate--20260516T031000000000Z-22222222222222222222222222222222.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(payload["findings"][0]["code"], "terminology_ambiguous_glossary_match")
            self.assertEqual(payload["findings"][0]["severity"], "warning")

    def test_glossary_suggest_from_tm_writes_report_without_mutating_glossary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            before = (root / "glossary.yaml").read_text(encoding="utf-8")
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            _insert_tm_record(root, canonical, "bye", "Au revoir")

            with stable_run_env("2026-05-16T03:20:00.000000Z", "3" * 32):
                code = run_cli(["glossary", "suggest", "--project-root", str(root), "--from-tm", "--target-locale", "fr-FR"])

            self.assertEqual(code, 0)
            self.assertEqual((root / "glossary.yaml").read_text(encoding="utf-8"), before)
            report = root / "reports" / "glossary" / "glossary_suggest--20260516T032000000000Z-33333333333333333333333333333333.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["suggestion_count"], 1)
            self.assertFalse(payload["summary"]["glossary_written"])


def _write_glossary(root: Path) -> None:
    (root / "glossary.yaml").write_text(
        yaml_dump(
            {
                "schema_version": "1.0",
                "project_id": "myapp",
                "glossary_version": "product-1",
                "terms": [
                    {
                        "id": "access-token",
                        "source": "Access token",
                        "targets": {"fr-fr": {"term": "jeton d'acces", "status": "approved"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _insert_tm_record(root: Path, canonical: dict, key: str, target_value: str) -> None:
    entry = canonical["entries"][key]
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        conn.execute(
            """
            INSERT INTO memory_entries (
                tm_record_id, project_id, key, source_locale, target_locale,
                source_content_hash, last_translated_source_hash, target_value,
                placeholder_signature, provenance, human_status, is_current,
                confidence_json, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"tm-{key}",
                canonical["project_id"],
                key,
                canonical["authoritative_locale"],
                "fr-fr",
                entry["content_hash"],
                entry["content_hash"],
                target_value,
                entry["placeholder_signature"],
                "human_reviewed",
                "reviewed",
                1,
                "{}",
                "{}",
                "2026-05-16T03:15:00.000000Z",
                "2026-05-16T03:15:00.000000Z",
            ),
        )


if __name__ == "__main__":
    unittest.main()
