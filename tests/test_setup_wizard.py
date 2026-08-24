from __future__ import annotations

import configparser
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.setup.wizard import (
    SetupAnswers,
    _openkneeboard_steps_text,
    _ptt_steps_text,
    build_config,
    run_setup_wizard,
    setup_help_text,
    write_setup_files,
)


class SetupWizardTests(unittest.TestCase):
    def test_build_config_contains_install_answers(self) -> None:
        answers = SetupAnswers(
            dcs_install_path=r"C:\Program Files\Eagle Dynamics\DCS World",
            dcs_saved_games_path=r"C:\Users\Pilot\Saved Games\DCS.openbeta",
            vr_platform="steamvr",
            openai_api_key="openai-test-key",
            gemini_api_key="gemini-test",
            keyboard_ptt_key="f13",
            joystick_backend="winmm",
            joystick_name="WINWING F18 TAKEOFF PANEL 2",
            joystick_button="0",
            joystick_winmm_device_id="4",
            input_device="2",
            buy_me_a_coffee_url="https://buymeacoffee.com/example",
        )

        config = build_config(answers)

        self.assertEqual(config["web"]["host"], "127.0.0.1")
        self.assertEqual(config["web"]["port"], "8765")
        self.assertEqual(config["dcs"]["install_path"], r"C:\Program Files\Eagle Dynamics\DCS World")
        self.assertEqual(config["dcs"]["saved_games_path"], r"C:\Users\Pilot\Saved Games\DCS.openbeta")
        self.assertEqual(config["vr"]["platform"], "steamvr")
        self.assertEqual(config["vr"]["managed_by_ai_copilot"], "false")
        self.assertEqual(config["openkneeboard"]["dashboard_url"], "http://127.0.0.1:8765")
        self.assertEqual(config["voice"]["joystick_backend"], "winmm")
        self.assertEqual(config["voice"]["joystick_winmm_device_id"], "4")
        self.assertEqual(config["voice"]["input_device"], "2")
        self.assertEqual(config["voice"]["transcription_provider"], "openai")
        self.assertEqual(config["voice"]["transcription_fallback_provider"], "gemini")
        self.assertEqual(config["voice"]["gemini_transcription_model"], "gemini-2.5-flash")
        self.assertEqual(config["donation"]["buy_me_a_coffee_url"], "https://buymeacoffee.com/example")
        self.assertNotIn("openai-test-key", str({section: dict(config[section]) for section in config.sections()}))
        self.assertNotIn("gemini-test", str({section: dict(config[section]) for section in config.sections()}))

    def test_write_setup_files_writes_config_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_setup_files(
                root,
                SetupAnswers(
                    dcs_install_path="",
                    dcs_saved_games_path=r"C:\Users\Pilot\Saved Games\DCS",
                    vr_platform="openxr-other",
                    openai_api_key="openai-test-key",
                    gemini_api_key="gemini-test",
                    keyboard_ptt_key="f13",
                    joystick_backend="winmm",
                    joystick_name="Panel",
                    joystick_button="0",
                    joystick_winmm_device_id="4",
                    input_device="",
                ),
            )

            config = configparser.ConfigParser()
            config.read(root / "config.ini", encoding="utf-8")

            self.assertEqual(config["voice"]["joystick_name"], "Panel")
            self.assertEqual(
                (root / ".env").read_text(encoding="utf-8"),
                "OPENAI_API_KEY=openai-test-key\nGEMINI_API_KEY=gemini-test\n",
            )

    def test_setup_wizard_runs_until_user_is_satisfied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            answers = iter(
                [
                    r"C:\Program Files\Eagle Dynamics\DCS World",
                    r"C:\Users\Pilot\Saved Games\DCS",
                    "openxr-pimax",
                    "openai-test-key",
                    "",
                    "f13",
                    "winmm",
                    "Panel",
                    "0",
                    "4",
                    "",
                    "",
                    "yes",
                ]
            )
            output: list[str] = []

            exit_code = run_setup_wizard(
                Path(temp_dir),
                input_func=lambda prompt: next(answers),
                print_func=output.append,
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(temp_dir) / "config.ini").exists())
            self.assertIn("Good. Start the app", "\n".join(output))

    def test_help_texts_include_user_actions(self) -> None:
        self.assertIn("Web Dashboard", _openkneeboard_steps_text())
        self.assertIn("--diagnose-joysticks", _ptt_steps_text())
        self.assertIn("--diagnose-audio", _ptt_steps_text())

    def test_setup_help_text_can_be_shown_after_install(self) -> None:
        text = setup_help_text()

        self.assertIn("DCS AI Copilot setup help", text)
        self.assertIn("OpenKneeboard setup", text)
        self.assertIn("DCS-BIOS setup help", text)
        self.assertIn("--dcs-bios-help", text)
        self.assertIn("PTT setup", text)
        self.assertIn("--backup-dcs", text)
        self.assertIn("Uninstall", text)
        self.assertIn("does not change VR settings", text)


if __name__ == "__main__":
    unittest.main()
