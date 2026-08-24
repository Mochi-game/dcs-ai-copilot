from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.setup.dcs_bios_help import (
    EXPORT_LUA_LINE,
    format_dcs_bios_setup_help,
    inspect_dcs_bios_setup,
)


class DcsBiosHelpTests(unittest.TestCase):
    def test_inspect_dcs_bios_setup_detects_export_lua_and_reference_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            saved_games = Path(temp_dir) / "Saved Games" / "DCS.openbeta"
            reference_dir = saved_games / "Scripts" / "DCS-BIOS" / "doc" / "json"
            reference_dir.mkdir(parents=True)
            export_lua = saved_games / "Scripts" / "Export.lua"
            export_lua.write_text(EXPORT_LUA_LINE + "\n", encoding="utf-8")

            status = inspect_dcs_bios_setup(saved_games)

        self.assertTrue(status.scripts_dir_exists)
        self.assertTrue(status.dcs_bios_dir_exists)
        self.assertTrue(status.reference_json_dir_exists)
        self.assertTrue(status.export_lua_exists)
        self.assertTrue(status.export_lua_mentions_dcs_bios)

    def test_format_dcs_bios_setup_help_includes_safe_manual_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status = inspect_dcs_bios_setup(Path(temp_dir) / "Saved Games" / "DCS")
            text = format_dcs_bios_setup_help(status)

        self.assertIn("DCS-BIOS setup help", text)
        self.assertIn("Version 2.0 still sends no cockpit commands", text)
        self.assertIn("does not edit DCS files automatically", text)
        self.assertIn("DCS-BIOS_x.y.z.zip", text)
        self.assertIn("Scripts\\DCS-BIOS\\BIOS.lua", text)
        self.assertIn("https://github.com/DCS-Skunkworks/dcs-bios/releases/latest", text)


if __name__ == "__main__":
    unittest.main()
