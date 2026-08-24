from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.setup.maintenance import (
    backup_dcs_saved_games,
    format_release_check_report,
    license_help,
    release_check_exit_code,
    run_release_check,
    uninstall_help,
)


class MaintenanceTests(unittest.TestCase):
    def test_backup_dcs_saved_games_copies_config_and_skips_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "DCS.openbeta"
            destination = root / "backup-disk"
            (source / "Config").mkdir(parents=True)
            (source / "fxo").mkdir()
            (source / "Config" / "options.lua").write_text("options", encoding="utf-8")
            (source / "fxo" / "cache.bin").write_text("cache", encoding="utf-8")

            backup_path = backup_dcs_saved_games(source, destination)

            self.assertTrue((backup_path / "Config" / "options.lua").exists())
            self.assertFalse((backup_path / "fxo").exists())

    def test_uninstall_help_mentions_project_folder(self) -> None:
        text = uninstall_help(Path(r"D:\Projects\DCS-AI-Copilot"))

        self.assertIn("Delete project folder", text)
        self.assertIn("DCS AI Copilot uninstall help", text)

    def test_license_help_describes_required_license_file(self) -> None:
        text = license_help(Path(r"D:\Projects\DCS-AI-Copilot"))

        self.assertIn("DCS AI Copilot license help", text)
        self.assertIn("currently uses the MIT License", text)
        self.assertIn("LICENSE", text)
        self.assertIn("MIT", text)
        self.assertIn("python main.py --release-check --release-version 2.0", text)

    def test_release_check_blocks_missing_license_and_donation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_minimal_release_tree(root, buy_me_a_coffee_url="")

            results = run_release_check(root, version="2.0")
            report = format_release_check_report(results)

        self.assertEqual(release_check_exit_code(results), 1)
        self.assertIn("[FAIL] LICENSE", report)
        self.assertIn("[FAIL] Buy Me a Coffee URL", report)

    def test_release_check_passes_when_public_release_inputs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_minimal_release_tree(root, buy_me_a_coffee_url="https://buymeacoffee.com/example")
            (root / "LICENSE").write_text(
                "MIT License\nCopyright (c) 2026 Michael Johnlin\n",
                encoding="utf-8",
            )

            results = run_release_check(root, version="2.0")
            report = format_release_check_report(results)

        self.assertEqual(release_check_exit_code(results), 0)
        self.assertIn("No blocking release issues found.", report)

    def test_release_check_blocks_license_template_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_minimal_release_tree(root, buy_me_a_coffee_url="https://buymeacoffee.com/example")
            (root / "LICENSE").write_text("Copyright (c) YEAR AUTHOR\n", encoding="utf-8")

            results = run_release_check(root, version="2.0")
            report = format_release_check_report(results)

        self.assertEqual(release_check_exit_code(results), 1)
        self.assertIn("LICENSE still looks like a template", report)


def _write_minimal_release_tree(root: Path, buy_me_a_coffee_url: str) -> None:
    (root / "release").mkdir(parents=True)
    (root / "config.ini").write_text(
        "\n".join(
            [
                "[donation]",
                f"buy_me_a_coffee_url = {buy_me_a_coffee_url}",
            ]
        ),
        encoding="utf-8",
    )
    (root / ".env.example").write_text("OPENAI_API_KEY=\nGEMINI_API_KEY=\n", encoding="utf-8")
    (root / ".gitignore").write_text(".env\n!.env.example\n", encoding="utf-8")
    (root / "README.md").write_text(
        "DCS-BIOS read-only. No cockpit commands. No hidden multiplayer data. No local AI.\n",
        encoding="utf-8",
    )
    (root / "release" / "DCS-AI-Copilot-Setup-2.0.exe").write_bytes(b"installer")
    (root / "release" / "RELEASE_NOTES-2.0.md").write_text(
        "DCS-BIOS read-only. No cockpit commands. No hidden multiplayer data.\n",
        encoding="utf-8",
    )
    import zipfile

    with zipfile.ZipFile(root / "release" / "DCS-AI-Copilot-portable-2.0.zip", "w") as archive:
        for name in (
            "DCS-AI-Copilot.exe",
            "LICENSE",
            ".env.example",
            "README.md",
            "docs/DCS_BIOS_SETUP.md",
            "docs/LICENSE_HELP.md",
            "docs/USER_SETUP_GUIDE.md",
            "Install-DCS-AI-Copilot.ps1",
            "Uninstall-DCS-AI-Copilot.ps1",
            "Prepare-GitHub-Release.ps1",
            "Prepare-Local-Git-Repository.ps1",
            "Test-Release-Smoke.ps1",
        ):
            archive.writestr(name, "placeholder")


if __name__ == "__main__":
    unittest.main()
