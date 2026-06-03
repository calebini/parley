from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import run_cli_capture


class LocaleReferenceTests(unittest.TestCase):
    def test_locale_list_prints_common_locale_table(self) -> None:
        code, stdout, _ = run_cli_capture(["locale", "list", "--query", "german"])

        self.assertEqual(code, 0)
        self.assertIn("language", stdout)
        self.assertIn("German", stdout)
        self.assertIn("de-DE", stdout)
        self.assertIn("de-de", stdout)
        self.assertIn("de.lproj", stdout)
        self.assertIn("values-de-rDE", stdout)

    def test_locale_list_json_outputs_suggestions(self) -> None:
        code, stdout, _ = run_cli_capture(["--output-format", "json", "locale", "list", "--query", "french canada"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout)
        self.assertEqual(payload["query"], "french canada")
        self.assertEqual(payload["locales"][0]["locale"], "fr-CA")
        self.assertEqual(payload["locales"][0]["stored_locale"], "fr-ca")


if __name__ == "__main__":
    unittest.main()
