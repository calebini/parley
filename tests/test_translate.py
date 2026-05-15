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
from parley.serialization import yaml_dump


class TranslateTests(unittest.TestCase):
    def test_translate_tm_only_reuses_memory_and_writes_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            _insert_tm_record(root, canonical, "bye", "Au revoir")
            _insert_tm_record(root, canonical, "hello", "Bonjour %@")

            with stable_run_env("2026-05-15T11:00:00.000000Z", "5" * 32):
                code = run_cli(
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

            self.assertEqual(code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "Au revoir";\n"hello" = "Bonjour %@";\n',
            )
            report = root / "reports" / "translation" / "translate--20260515T110000000000Z-55555555555555555555555555555555.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "not_applicable")
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["reused", "reused"])
            self.assertEqual(payload["summary"]["reused_count"], 2)

    def test_translate_tm_only_reports_tm_miss_without_target_writeback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            _insert_tm_record(root, canonical, "hello", "Bonjour %@")

            with stable_run_env("2026-05-15T12:00:00.000000Z", "6" * 32):
                code = run_cli(
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

            self.assertEqual(code, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "")
            report = root / "reports" / "translation" / "translate--20260515T120000000000Z-66666666666666666666666666666666.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            outcomes = {item["key"]: item for item in payload["per_key_outcomes"]}
            self.assertEqual(outcomes["bye"]["outcome"], "failed")
            self.assertEqual(outcomes["bye"]["category"], "tm_miss")
            self.assertEqual(outcomes["hello"]["outcome"], "reused")

    def test_translate_provider_required_no_provider_writes_deterministic_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            _add_empty_target(root)

            with stable_run_env("2026-05-15T13:00:00.000000Z", "7" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--no-provider",
                    ]
                )

            self.assertEqual(code, 2)
            report = root / "reports" / "translation" / "translate--20260515T130000000000Z-77777777777777777777777777777777.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure_category"], "provider_disallowed")
            self.assertEqual(payload["provider_status"], "skipped")
            self.assertEqual(payload["provider_skip_reason"], "no_provider")
            self.assertEqual(
                [item["category"] for item in payload["per_key_outcomes"]],
                ["provider_disallowed", "provider_disallowed"],
            )


def _populate_context_anchor(root: Path) -> None:
    canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
    anchor = {
        "schema_version": "1.0",
        "project_id": canonical["project_id"],
        "authoritative_locale": canonical["authoritative_locale"],
        "project_context": {"description": "Demo app"},
        "entries": {
            key: {"context": f"UI copy for {key}"}
            for key in sorted(canonical["entries"])
        },
    }
    (root / "context-anchor.yaml").write_text(yaml_dump(anchor), encoding="utf-8")


def _add_empty_target(root: Path) -> Path:
    target = root / "fr.lproj" / "Localizable.strings"
    target.parent.mkdir()
    target.write_text("", encoding="utf-8")
    with stable_run_env("2026-05-15T10:30:00.000000Z", "8" * 32):
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
    if code != 1:
        raise AssertionError(f"expected empty target add to report blocking findings, got {code}")
    return target


def _insert_tm_record(root: Path, canonical: dict, key: str, target_value: str) -> None:
    entry = canonical["entries"][key]
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        conn.execute(
            """
            INSERT INTO memory_entries (
                tm_record_id, project_id, key, source_locale, target_locale,
                source_content_hash, last_translated_source_hash, target_value,
                placeholder_signature, provenance, human_status, is_current, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                "2026-05-15T09:00:00.000000Z",
            ),
        )


if __name__ == "__main__":
    unittest.main()
