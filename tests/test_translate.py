from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import textwrap
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
            self.assertEqual(_summary_flags(payload), (True, True, False, "dummy", "not_applicable"))

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
            self.assertEqual(_summary_flags(payload), (False, False, False, "dummy", "not_applicable"))

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
            self.assertEqual(_summary_flags(payload), (False, False, False, "dummy", "skipped"))
            self.assertEqual(
                [item["category"] for item in payload["per_key_outcomes"]],
                ["provider_disallowed", "provider_disallowed"],
            )

    def test_translate_provider_only_dummy_generates_and_writes_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)

            with stable_run_env("2026-05-15T14:00:00.000000Z", "9" * 32):
                code = run_cli(
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

            self.assertEqual(code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "[fr-fr] Bye";\n"hello" = "[fr-fr] Hello %@";\n',
            )
            report = root / "reports" / "translation" / "translate--20260515T140000000000Z-99999999999999999999999999999999.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "used")
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["generated", "generated"])
            self.assertEqual(payload["summary"]["generated_count"], 2)
            self.assertEqual(_summary_flags(payload), (True, True, False, "dummy", "used"))

    def test_translate_tm_then_provider_reuses_and_generates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            _insert_tm_record(root, canonical, "hello", "Bonjour %@")

            with stable_run_env("2026-05-15T15:00:00.000000Z", "a" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "tm_then_provider",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "[fr-fr] Bye";\n"hello" = "Bonjour %@";\n',
            )
            report = root / "reports" / "translation" / "translate--20260515T150000000000Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "used")
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["generated", "reused"])
            self.assertEqual(payload["summary"]["generated_count"], 1)
            self.assertEqual(payload["summary"]["reused_count"], 1)
            self.assertEqual(_summary_flags(payload), (True, True, False, "dummy", "used"))

    def test_translate_provider_dry_run_writes_report_without_target_writeback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)

            with stable_run_env("2026-05-15T16:00:00.000000Z", "b" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "")
            report = root / "reports" / "translation" / "translate--20260515T160000000000Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "used")
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["generated", "generated"])
            self.assertEqual(_summary_flags(payload), (False, False, True, "dummy", "used"))
            self.assertEqual(_tm_rows(root), [])

    def test_translate_generated_writeback_populates_tm_for_later_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)

            with stable_run_env("2026-05-15T17:00:00.000000Z", "c" * 32):
                first_code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                    ]
                )
            self.assertEqual(first_code, 0)
            rows_after_generate = _tm_rows(root)
            self.assertEqual(
                [(row["key"], row["target_value"], row["provenance"], row["human_status"], row["is_current"]) for row in rows_after_generate],
                [
                    ("bye", "[fr-fr] Bye", "machine_generated", "draft", 1),
                    ("hello", "[fr-fr] Hello %@", "machine_generated", "draft", 1),
                ],
            )
            self.assertEqual({row["updated_at"] for row in rows_after_generate}, {"2026-05-15T17:00:00.000000Z"})
            self.assertEqual({row["confidence_json"] for row in rows_after_generate}, {"{}"})
            self.assertEqual({row["metadata_json"] for row in rows_after_generate}, {"{}"})

            target.write_text("", encoding="utf-8")
            with stable_run_env("2026-05-15T18:00:00.000000Z", "d" * 32):
                second_code = run_cli(
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
            self.assertEqual(second_code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "[fr-fr] Bye";\n"hello" = "[fr-fr] Hello %@";\n',
            )
            report = root / "reports" / "translation" / "translate--20260515T180000000000Z-dddddddddddddddddddddddddddddddd.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["reused", "reused"])
            self.assertEqual(_summary_flags(payload), (True, True, False, "dummy", "not_applicable"))
            self.assertEqual({row["updated_at"] for row in _tm_rows(root)}, {"2026-05-15T17:00:00.000000Z"})

    def test_translate_reused_writeback_marks_selected_record_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            _add_empty_target(root)
            canonical = json.loads((root / "canonical-inventory.json").read_text(encoding="utf-8"))
            _insert_tm_record(root, canonical, "hello", "Bonjour ancien %@", record_id="tm-hello-old", is_current=1)
            _insert_tm_record(root, canonical, "hello", "Bonjour %@", record_id="tm-hello-new", is_current=0, updated_at="2026-05-15T10:00:00.000000Z")
            _insert_tm_record(root, canonical, "bye", "Au revoir")

            with stable_run_env("2026-05-15T19:00:00.000000Z", "e" * 32):
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
            rows = {row["tm_record_id"]: row for row in _tm_rows(root)}
            self.assertEqual(rows["tm-hello-new"]["is_current"], 1)
            self.assertEqual(rows["tm-hello-new"]["updated_at"], "2026-05-15T19:00:00.000000Z")
            self.assertEqual(rows["tm-hello-old"]["is_current"], 0)

    def test_translate_command_json_provider_generates_with_fake_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            provider = _fake_provider_script(
                root,
                """
                import json
                import sys
                request = json.loads(sys.stdin.read())
                entries = [
                    {
                        "key": entry["key"],
                        "status": "translated",
                        "translated_text": "[cli] " + entry["source_text"],
                        "failure_reason": None,
                    }
                    for entry in request["entries"]
                ]
                print(json.dumps({
                    "schema_version": "1.0",
                    "request_id": request["request_id"],
                    "provider_id": request["provider_id"],
                    "status": "ok",
                    "entries": entries,
                    "provider_metadata": None,
                }))
                """,
            )

            with stable_run_env("2026-05-15T20:00:00.000000Z", "f" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--provider",
                        "command-json",
                        "--provider-command",
                        str(provider),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "[cli] Bye";\n"hello" = "[cli] Hello %@";\n',
            )
            report = root / "reports" / "translation" / "translate--20260515T200000000000Z-ffffffffffffffffffffffffffffffff.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "used")
            self.assertEqual(payload["summary"]["provider_id"], "command-json")
            self.assertEqual([item["outcome"] for item in payload["per_key_outcomes"]], ["generated", "generated"])

    def test_translate_command_json_provider_failure_does_not_write_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            provider = _fake_provider_script(root, "import sys\nsys.exit(9)\n")

            with stable_run_env("2026-05-15T21:00:00.000000Z", "1" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--provider",
                        "command-json",
                        "--provider-command",
                        str(provider),
                    ]
                )

            self.assertEqual(code, 4)
            self.assertEqual(target.read_text(encoding="utf-8"), "")
            report = root / "reports" / "translation" / "translate--20260515T210000000000Z-11111111111111111111111111111111.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_status"], "failed")
            self.assertEqual(payload["provider_failure_category"], "provider_process_failed")
            self.assertEqual(
                [item["category"] for item in payload["per_key_outcomes"]],
                ["provider_failed", "provider_not_attempted_after_failure"],
            )

    def test_translate_command_json_missing_command_is_usage_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)

            with stable_run_env("2026-05-15T22:00:00.000000Z", "2" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--provider",
                        "command-json",
                    ]
                )

            self.assertEqual(code, 2)
            self.assertEqual(target.read_text(encoding="utf-8"), "")
            report = root / "reports" / "translation" / "translate--20260515T220000000000Z-22222222222222222222222222222222.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["failure_category"], "provider_disallowed")
            self.assertEqual(payload["provider_status"], "skipped")
            self.assertEqual(payload["provider_skip_reason"], "invalid_configuration")
            self.assertEqual(payload["provider_failure_category"], "invalid_configuration")

    def test_translate_command_json_provider_uses_output_file_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)
            _populate_context_anchor(root)
            target = _add_empty_target(root)
            provider = _fake_provider_script(
                root,
                """
                import json
                import os
                request = json.loads(open(os.environ["PARLEY_REQUEST_PATH"], encoding="utf-8").read())
                entries = [
                    {
                        "key": entry["key"],
                        "status": "translated",
                        "translated_text": "[file] " + entry["source_text"],
                        "failure_reason": None,
                    }
                    for entry in request["entries"]
                ]
                with open(os.environ["PARLEY_RESPONSE_PATH"], "w", encoding="utf-8") as output:
                    json.dump({
                        "schema_version": "1.0",
                        "request_id": request["request_id"],
                        "provider_id": request["provider_id"],
                        "status": "ok",
                        "entries": entries,
                        "provider_metadata": None,
                    }, output)
                """,
            )

            with stable_run_env("2026-05-15T23:00:00.000000Z", "3" * 32):
                code = run_cli(
                    [
                        "translate",
                        "--project-root",
                        str(root),
                        "--target-locale",
                        "fr-FR",
                        "--reuse-mode",
                        "provider_only",
                        "--provider",
                        "command-json",
                        "--provider-command",
                        str(provider),
                        "--provider-request-delivery",
                        "output_file",
                        "--provider-response-mode",
                        "output_file_json",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                '"bye" = "[file] Bye";\n"hello" = "[file] Hello %@";\n',
            )
            self.assertEqual(list((root / ".parley/provider-io").glob("*.json")), [])


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


def _insert_tm_record(
    root: Path,
    canonical: dict,
    key: str,
    target_value: str,
    *,
    record_id: str | None = None,
    is_current: int = 1,
    updated_at: str = "2026-05-15T09:00:00.000000Z",
) -> None:
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
                record_id or f"tm-{key}",
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
                is_current,
                "{}",
                "{}",
                updated_at,
                updated_at,
            ),
        )


def _tm_rows(root: Path) -> list[dict]:
    with sqlite3.connect(root / "translation-memory.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT tm_record_id, key, target_value, provenance, human_status, is_current,
                       confidence_json, metadata_json, created_at, updated_at
                FROM memory_entries
                ORDER BY key, tm_record_id
                """
            )
        ]


def _summary_flags(payload: dict) -> tuple[bool, bool, bool, str, str]:
    summary = payload["summary"]
    return (
        summary["written_target"],
        summary["tm_written"],
        summary["dry_run"],
        summary["provider_id"],
        summary["provider_status"],
    )


def _fake_provider_script(root: Path, source: str) -> Path:
    path = root / "fake_provider"
    path.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


if __name__ == "__main__":
    unittest.main()
