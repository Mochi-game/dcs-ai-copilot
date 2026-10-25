from __future__ import annotations

import sys
import tempfile
import unittest
import subprocess
import socket
import time
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from main import default_release_project_root


class CliTests(unittest.TestCase):
    def test_background_survives_closed_stdin_and_serves_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_root = Path(temp_dir)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            (config_root / "config.ini").write_text(
                f"[web]\nport = {port}\n[voice]\nenabled = false\n"
                "[dcs_bios]\nenabled = false\n", encoding="utf-8"
            )
            script = (
                "import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(ROOT)!r}); import main; "
                f"main.ensure_config_root = lambda: Path({temp_dir!r}); "
                "sys.argv = ['main.py', '--background']; raise SystemExit(main.main())"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), "Background app exited on closed stdin")
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=0.5) as response:
                            state = json.load(response)
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail("Background dashboard did not start")
                self.assertEqual(state["voice"]["status"], "DISABLED")
                time.sleep(0.2)
                self.assertIsNone(process.poll())
            finally:
                process.terminate()
                process.communicate(timeout=5)

    def test_default_release_project_root_finds_project_from_dist_app(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "dist" / "DCS-AI-Copilot"
            (root / "release").mkdir(parents=True)
            app_root.mkdir(parents=True)

            self.assertEqual(default_release_project_root(app_root), root)


if __name__ == "__main__":
    unittest.main()
