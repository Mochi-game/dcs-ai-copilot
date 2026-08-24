from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from main import default_release_project_root


class CliTests(unittest.TestCase):
    def test_default_release_project_root_finds_project_from_dist_app(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "dist" / "DCS-AI-Copilot"
            (root / "release").mkdir(parents=True)
            app_root.mkdir(parents=True)

            self.assertEqual(default_release_project_root(app_root), root)


if __name__ == "__main__":
    unittest.main()
