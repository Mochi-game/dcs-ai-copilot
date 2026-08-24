from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_optional_dcs_install_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dcs_install = root / "DCS World"
            config_file = root / "config.ini"
            config_file.write_text(
                "\n".join(
                    [
                        "[dcs]",
                        f"install_path = {dcs_install}",
                        "saved_games_path =",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_file)

        self.assertEqual(config.dcs_install_path, dcs_install)

    def test_load_config_allows_missing_dcs_install_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.ini"
            config_file.write_text("[dcs]\ninstall_path =\n", encoding="utf-8")

            config = load_config(config_file)

        self.assertIsNone(config.dcs_install_path)

    def test_load_config_reads_transcription_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.ini"
            config_file.write_text(
                "\n".join(
                    [
                        "[voice]",
                        "transcription_provider = openai",
                        "transcription_fallback_provider = gemini",
                        "transcription_model = gpt-4o-mini-transcribe",
                        "gemini_transcription_model = gemini-2.5-flash",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_file)

        self.assertEqual(config.voice_transcription_provider, "openai")
        self.assertEqual(config.voice_transcription_fallback_provider, "gemini")
        self.assertEqual(config.voice_transcription_model, "gpt-4o-mini-transcribe")
        self.assertEqual(config.voice_gemini_transcription_model, "gemini-2.5-flash")

    def test_load_config_reads_vr_platform_without_managing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.ini"
            config_file.write_text(
                "\n".join(
                    [
                        "[vr]",
                        "platform = oculus",
                        "managed_by_ai_copilot = false",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_file)

        self.assertEqual(config.vr_platform, "oculus")
        self.assertFalse(config.vr_managed_by_ai_copilot)

    def test_load_config_defaults_vr_to_openxr_other(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.ini"
            config_file.write_text("", encoding="utf-8")

            config = load_config(config_file)

        self.assertEqual(config.vr_platform, "openxr-other")
        self.assertFalse(config.vr_managed_by_ai_copilot)


if __name__ == "__main__":
    unittest.main()
