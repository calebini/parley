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
from parley.parsers import parse_localization


class LintTests(unittest.TestCase):
    def test_lint_audit_reports_mojibake_in_target_and_tm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root, source_text='"secure" = "Secure Code";\n')
            target = _add_target(root, "hu-HU", '"secure" = "BiztonsÃ¡gi kÃ³d";\n')
            _insert_tm_record(root, "secure", "hu-hu", "BiztonsÃ¡gi kÃ³d")

            with stable_run_env("2026-05-16T03:00:00.000000Z", "1" * 32):
                code = run_cli(["lint", "audit", "--project-root", str(root)])

            self.assertEqual(code, 1)
            report = root / "reports" / "lint" / "lint_audit--20260516T030000000000Z-11111111111111111111111111111111.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["finding_count"], 1)
            self.assertEqual(payload["summary"]["fixable_count"], 1)
            self.assertEqual(payload["summary"]["scope"], "files")
            self.assertEqual({item["code"] for item in payload["findings"]}, {"mojibake_suspected"})
            self.assertEqual(target.read_text(encoding="utf-8"), '"secure" = "BiztonsÃ¡gi kÃ³d";\n')

            with stable_run_env("2026-05-16T03:05:00.000000Z", "4" * 32):
                all_code = run_cli(["lint", "audit", "--project-root", str(root), "--scope", "all"])

            self.assertEqual(all_code, 1)
            all_report = root / "reports" / "lint" / "lint_audit--20260516T030500000000Z-44444444444444444444444444444444.json"
            all_payload = json.loads(all_report.read_text(encoding="utf-8"))
            self.assertEqual(all_payload["summary"]["finding_count"], 2)
            self.assertEqual(all_payload["summary"]["fixable_count"], 2)

    def test_lint_fix_repairs_mojibake_in_target_and_tm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root, source_text='"secure" = "Secure Code";\n')
            target = _add_target(root, "hu-HU", '"secure" = "BiztonsÃ¡gi kÃ³d";\n')
            _insert_tm_record(root, "secure", "hu-hu", "BiztonsÃ¡gi kÃ³d")

            with stable_run_env("2026-05-16T03:10:00.000000Z", "2" * 32):
                dry_code = run_cli(["lint", "fix", "--project-root", str(root), "--dry-run"])

            self.assertEqual(dry_code, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), '"secure" = "BiztonsÃ¡gi kÃ³d";\n')

            with stable_run_env("2026-05-16T03:20:00.000000Z", "3" * 32):
                code = run_cli(["lint", "fix", "--project-root", str(root)])

            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), '"secure" = "Biztonsági kód";\n')
            entries = parse_localization(target.read_text(encoding="utf-8"), "ios_strings")
            self.assertEqual(entries.entries[0].value, "Biztonsági kód")
            with sqlite3.connect(root / "translation-memory.sqlite") as conn:
                value = conn.execute(
                    "SELECT target_value FROM memory_entries WHERE target_locale='hu-hu' AND key='secure' AND is_current=1"
                ).fetchone()[0]
            self.assertEqual(value, "Biztonsági kód")
            report = root / "reports" / "lint" / "lint_fix--20260516T032000000000Z-33333333333333333333333333333333.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["finding_count"], 0)
            self.assertEqual(payload["summary"]["applied_count"], 1)


def _add_target(root: Path, locale: str, content: str) -> Path:
    folder = locale.split("-")[0].lower()
    target = root / f"{folder}.lproj" / "Localizable.strings"
    target.parent.mkdir()
    target.write_text(content, encoding="utf-8")
    code = run_cli(
        [
            "localization",
            "add",
            str(target),
            "--project-root",
            str(root),
            "--locale",
            locale,
        ]
    )
    if code not in {0, 1}:
        raise AssertionError(f"target add failed with {code}")
    return target


def _insert_tm_record(root: Path, key: str, target_locale: str, target_value: str) -> None:
    canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
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
                target_locale,
                entry["content_hash"],
                entry["content_hash"],
                target_value,
                entry["placeholder_signature"],
                "human_reviewed",
                "reviewed",
                1,
                "{}",
                "{}",
                "2026-05-16T03:00:00.000000Z",
                "2026-05-16T03:00:00.000000Z",
            ),
        )


if __name__ == "__main__":
    unittest.main()
