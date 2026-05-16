from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import init_project, run_cli_capture


class ContextSeedTests(unittest.TestCase):
    def test_context_seed_populates_per_key_placeholder_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(root)

            code, stdout, _ = run_cli_capture(
                ["--output-format", "json", "context", "seed", "--project-root", str(root)]
            )

            self.assertEqual(code, 0)
            self.assertIn('"entry_count": 2', stdout)
            anchor = (root / "context-anchor.yaml").read_text(encoding="utf-8")
            self.assertIn('hello:', anchor)
            self.assertIn('context: "Placeholder context for hello (placeholder)."', anchor)
            self.assertIn('bye:', anchor)
            self.assertIn('context: "Placeholder context for bye (placeholder)."', anchor)


if __name__ == "__main__":
    unittest.main()
