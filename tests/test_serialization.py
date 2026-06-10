from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parley.serialization import yaml_load


class SerializationTests(unittest.TestCase):
    def test_yaml_load_accepts_literal_block_scalar(self) -> None:
        data = yaml_load(
            """schema_version: "1.0"
project_context:
  description: |
    First line.
    Second line.

    Third paragraph.
"""
        )

        self.assertEqual(
            data["project_context"]["description"],
            "First line.\nSecond line.\n\nThird paragraph.\n",
        )

    def test_yaml_load_accepts_folded_block_scalar(self) -> None:
        data = yaml_load(
            """entries:
  About_Menu:
    context: >
      Menu item that opens the About screen
      for the application.
  Product_Name:
    context: >-
      Official product name displayed
      throughout the application.
"""
        )

        self.assertEqual(
            data["entries"]["About_Menu"]["context"],
            "Menu item that opens the About screen for the application.\n",
        )
        self.assertEqual(
            data["entries"]["Product_Name"]["context"],
            "Official product name displayed throughout the application.",
        )


if __name__ == "__main__":
    unittest.main()
