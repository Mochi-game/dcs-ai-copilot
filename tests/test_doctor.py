from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.setup.doctor import CheckResult, format_doctor_report, run_doctor
from dcs_ai_copilot.setup.wizard import SetupAnswers, write_setup_files


class DoctorTests(unittest.TestCase):
    def test_missing_config_is_blocking_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_doctor(Path(temp_dir) / "missing.ini")

        self.assertEqual(results[0].name, "Config")
        self.assertEqual(results[0].status, "FAIL")
        self.assertIn("--setup", results[0].action)

    def test_format_report_lists_actions(self) -> None:
        report = format_doctor_report(
            [
                CheckResult("OpenAI API key", "FAIL", "Missing", "Add .env"),
                CheckResult("Dashboard port", "OK", "Available"),
            ]
        )

        self.assertIn("[FAIL] OpenAI API key: Missing", report)
        self.assertIn("Fix: Add .env", report)
        self.assertIn("One or more required setup items need attention.", report)

    def test_dcs_install_path_is_checked_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_setup_files(
                root,
                SetupAnswers(
                    dcs_install_path="",
                    dcs_saved_games_path=str(root / "Saved Games" / "DCS"),
                    vr_platform="openxr-other",
                    openai_api_key="",
                    gemini_api_key="",
                    keyboard_ptt_key="f13",
                    joystick_backend="winmm",
                    joystick_name="Panel",
                    joystick_button="0",
                    joystick_winmm_device_id="auto",
                    input_device="",
                ),
            )

            results = run_doctor(root / "config.ini")

        dcs_result = next(result for result in results if result.name == "DCS World install path")
        self.assertEqual(dcs_result.status, "WARN")
        self.assertIn("Run setup", dcs_result.action)
        export_result = next(result for result in results if result.name == "DCS-BIOS Export.lua")
        self.assertEqual(export_result.status, "WARN")
        self.assertIn("--dcs-bios-help", export_result.action)

    def test_dcs_bios_export_lua_is_ok_when_it_loads_dcs_bios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saved_games = root / "Saved Games" / "DCS"
            (saved_games / "Scripts").mkdir(parents=True)
            (saved_games / "Scripts" / "Export.lua").write_text(
                r"dofile(lfs.writedir() .. [[Scripts\DCS-BIOS\BIOS.lua]])",
                encoding="utf-8",
            )
            write_setup_files(
                root,
                SetupAnswers(
                    dcs_install_path="",
                    dcs_saved_games_path=str(saved_games),
                    vr_platform="openxr-other",
                    openai_api_key="",
                    gemini_api_key="",
                    keyboard_ptt_key="f13",
                    joystick_backend="winmm",
                    joystick_name="Panel",
                    joystick_button="0",
                    joystick_winmm_device_id="auto",
                    input_device="",
                ),
            )

            results = run_doctor(root / "config.ini")

        export_result = next(result for result in results if result.name == "DCS-BIOS Export.lua")
        self.assertEqual(export_result.status, "OK")

    def test_dcs_install_path_is_ok_when_dcs_exe_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dcs_install = root / "DCS World"
            (dcs_install / "bin").mkdir(parents=True)
            (dcs_install / "bin" / "DCS.exe").write_text("", encoding="utf-8")
            write_setup_files(
                root,
                SetupAnswers(
                    dcs_install_path=str(dcs_install),
                    dcs_saved_games_path=str(root / "Saved Games" / "DCS"),
                    vr_platform="steamvr",
                    openai_api_key="",
                    gemini_api_key="",
                    keyboard_ptt_key="f13",
                    joystick_backend="winmm",
                    joystick_name="Panel",
                    joystick_button="0",
                    joystick_winmm_device_id="auto",
                    input_device="",
                ),
            )

            results = run_doctor(root / "config.ini")

        dcs_result = next(result for result in results if result.name == "DCS World install path")
        self.assertEqual(dcs_result.status, "OK")
        self.assertEqual(dcs_result.detail, str(dcs_install))
        vr_result = next(result for result in results if result.name == "VR platform")
        self.assertEqual(vr_result.status, "OK")
        self.assertIn("steamvr", vr_result.detail)
        self.assertIn("does not change VR settings", vr_result.detail)


if __name__ == "__main__":
    unittest.main()
