from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import init_project


class ContextAnchorInitTests(unittest.TestCase):
    def test_project_init_scaffolds_blank_per_key_context_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)

            anchor = (root / "context-anchor.yaml").read_text(encoding="utf-8")
            self.assertIn('hello:', anchor)
            self.assertIn('bye:', anchor)
            self.assertEqual(anchor.count('context: ""'), 2)


if __name__ == "__main__":
    unittest.main()
