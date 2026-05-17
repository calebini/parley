from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parley.errors import ParserError
from parley.parsers import ParsedEntry, parse_localization, serialize_localization


class ParserTests(unittest.TestCase):
    def test_android_xml_round_trips_escaping_and_placeholders(self) -> None:
        content = """<resources>
    <string name="cta">Upgrade &amp; keep {plan}</string>
    <string name="greeting">Hello, %1$s</string>
    <string name="count">%d tasks</string>
</resources>
"""
        parsed = parse_localization(content, "android_xml")
        by_key = {entry.key: entry for entry in parsed.entries}
        self.assertEqual(by_key["cta"].value, "Upgrade & keep {plan}")
        self.assertEqual(by_key["cta"].placeholder_signature, "{plan}")
        self.assertEqual(by_key["greeting"].placeholder_signature, "%1$s")
        self.assertEqual(by_key["count"].placeholder_signature, "%d")

        serialized = serialize_localization(parsed.entries, "android_xml")
        self.assertIn('<string name="cta">Upgrade &amp; keep {plan}</string>', serialized)
        reparsed = parse_localization(serialized, "android_xml")
        self.assertEqual(
            [(entry.key, entry.value, entry.placeholder_signature) for entry in reparsed.entries],
            [(entry.key, entry.value, entry.placeholder_signature) for entry in parsed.entries],
        )

    def test_ios_strings_round_trips_escaping_and_placeholders(self) -> None:
        content = '"quote" = "Say \\"Hello\\" to %@";\n"count" = "%d tasks";\n'
        parsed = parse_localization(content, "ios_strings")
        serialized = serialize_localization(parsed.entries, "ios_strings")
        self.assertIn('"quote" = "Say \\"Hello\\" to %@";', serialized)
        reparsed = parse_localization(serialized, "ios_strings")
        self.assertEqual(
            [(entry.key, entry.value, entry.placeholder_signature) for entry in reparsed.entries],
            [(entry.key, entry.value, entry.placeholder_signature) for entry in parsed.entries],
        )

    def test_duplicate_keys_are_rejected_for_ios_and_android(self) -> None:
        with self.assertRaisesRegex(ParserError, "duplicate localization key: title"):
            parse_localization('"title" = "One";\n"title" = "Two";\n', "ios_strings")
        with self.assertRaisesRegex(ParserError, "duplicate localization key: title"):
            parse_localization(
                '<resources><string name="title">One</string><string name="title">Two</string></resources>',
                "android_xml",
            )

    def test_malformed_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ParserError, "invalid ios_strings entry"):
            parse_localization('"title" = "Missing semicolon"\n', "ios_strings")
        with self.assertRaisesRegex(ParserError, "android_xml root must be <resources>"):
            parse_localization("<strings></strings>", "android_xml")
        with self.assertRaisesRegex(ParserError, "missing name"):
            parse_localization("<resources><string>Untitled</string></resources>", "android_xml")

    def test_unsupported_format_is_rejected_for_parse_and_serialize(self) -> None:
        with self.assertRaisesRegex(ParserError, "unsupported localization format"):
            parse_localization("", "po")
        with self.assertRaisesRegex(ParserError, "unsupported localization format"):
            serialize_localization([ParsedEntry("title", "Title", [])], "po")


if __name__ == "__main__":
    unittest.main()
