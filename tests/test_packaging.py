from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_gitignore_excludes_secrets_and_build_outputs(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (
            ".env",
            ".env.*",
            ".build-venv/",
            "build/",
            "dist/",
            "release/",
            "logs/",
            "kneeboard.html",
            "*.spec",
        ):
            self.assertIn(pattern, gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_env_example_documents_required_keys_without_secrets(self) -> None:
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("OPENAI_API_KEY=", env_example)
        self.assertIn("GEMINI_API_KEY=", env_example)
        self.assertNotIn("sk-", env_example)
        self.assertNotIn("AIza", env_example)

    def test_project_has_mit_license(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Michael Johnlin", license_text)
        self.assertIn("released under the MIT License", readme)

    def test_requirements_include_cloud_speech_providers(self) -> None:
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("openai", requirements)
        self.assertIn("google-genai", requirements)

    def test_user_guide_covers_installer_and_manual_env_setup(self) -> None:
        guide = (ROOT / "docs" / "USER_SETUP_GUIDE.md").read_text(encoding="utf-8")

        self.assertIn("DCS-AI-Copilot-Setup-0.1.0.exe", guide)
        self.assertIn("DCS AI Copilot > First-time Setup", guide)
        self.assertIn(".env.example", guide)
        self.assertIn("DCS AI Copilot > Uninstall DCS AI Copilot", guide)
        self.assertIn("VR platform/headset", guide)
        self.assertIn("does not change OpenXR", guide)

    def test_public_default_config_does_not_pin_local_joystick_id(self) -> None:
        config = (ROOT / "config.ini").read_text(encoding="utf-8")

        self.assertIn("joystick_winmm_device_id = auto", config)
        self.assertNotIn("joystick_winmm_device_id = 4", config)
        self.assertIn("[vr]", config)
        self.assertIn("platform = openxr-other", config)
        self.assertIn("managed_by_ai_copilot = false", config)

    def test_windows_build_script_creates_release_assets(self) -> None:
        script = (ROOT / "packaging" / "windows" / "build_windows.ps1").read_text(encoding="utf-8")

        self.assertIn("Compress-Archive", script)
        self.assertIn("DCS-AI-Copilot-portable-$Version.zip", script)
        self.assertIn("DCS-AI-Copilot.generated.iss", script)
        self.assertIn("ISCC.exe", script)
        self.assertIn("RequireInstaller", script)
        self.assertIn("RequireLicense", script)
        self.assertIn('Join-Path $ProjectRoot "LICENSE"', script)
        self.assertIn("DCS-AI-Copilot-Setup-$Version.exe", script)
        self.assertIn("--paths \"src\"", script)
        self.assertIn('--collect-submodules "google.genai"', script)
        self.assertIn("Install-DCS-AI-Copilot.ps1", script)
        self.assertIn("Uninstall-DCS-AI-Copilot.ps1", script)
        self.assertIn("Prepare-GitHub-Release.ps1", script)
        self.assertIn("Prepare-Local-Git-Repository.ps1", script)
        self.assertIn("Test-Release-Smoke.ps1", script)
        self.assertIn('Join-Path $ProjectRoot "README.md"', script)
        self.assertIn('Join-Path $ProjectRoot ".env.example"', script)
        self.assertIn('Join-Path $ProjectRoot "docs"', script)

    def test_prepare_github_release_script_gates_final_publish(self) -> None:
        script = (ROOT / "packaging" / "windows" / "Prepare-GitHub-Release.ps1").read_text(encoding="utf-8")

        self.assertIn("Parameter(Mandatory = $true)", script)
        self.assertIn("BuyMeACoffeeUrl", script)
        self.assertIn("LICENSE is missing", script)
        self.assertIn("-RequireInstaller", script)
        self.assertIn("-RequireLicense", script)
        self.assertIn("--release-check", script)
        self.assertIn("git push -u origin main", script)
        self.assertIn("Prepare-Local-Git-Repository.ps1", script)
        self.assertIn("DCS-AI-Copilot-Setup-$Version.exe", script)

    def test_prepare_local_git_repository_script_guards_private_files(self) -> None:
        script = (ROOT / "packaging" / "windows" / "Prepare-Local-Git-Repository.ps1").read_text(encoding="utf-8")

        self.assertIn("GitUserName", script)
        self.assertIn("GitUserEmail", script)
        self.assertIn("GitHubUser", script)
        self.assertIn("Test-GitCommand", script)
        self.assertIn("Get-GitOutputOrEmpty", script)
        self.assertIn("python main.py --release-check", script)
        self.assertIn("Invoke-Git add .", script)
        self.assertIn(".env", script)
        self.assertIn('$name -ne ".env.example"', script)
        self.assertIn("Refusing to commit", script)
        self.assertIn("git push -u", script)
        self.assertIn("GitHub Release ${TagName}:", script)

    def test_inno_template_has_generated_placeholders_and_shortcuts(self) -> None:
        template = (ROOT / "packaging" / "windows" / "DCS-AI-Copilot.iss.template").read_text(encoding="utf-8")

        self.assertIn("__APP_VERSION__", template)
        self.assertIn("__APP_PUBLISHER__", template)
        self.assertIn("__APP_ID__", template)
        self.assertIn("Check Installation", template)
        self.assertIn("--doctor", template)
        self.assertIn("Audio Diagnostics", template)
        self.assertIn("--diagnose-audio", template)
        self.assertIn("License Help", template)
        self.assertIn("--license-help", template)
        self.assertIn("Release Check", template)
        self.assertIn("--release-check", template)
        self.assertIn("OutputDir=..\\..\\release", template)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\DCS AI Copilot", template)
        self.assertIn("PrivilegesRequired=lowest", template)
        self.assertIn("{uninstallexe}", template)
        self.assertIn("{userdesktop}\\DCS AI Copilot", template)

    def test_github_workflow_uploads_release_artifacts(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("build_windows.ps1", workflow)
        self.assertIn("choco install innosetup", workflow)
        self.assertIn("-RequireInstaller", workflow)
        self.assertIn("require_license", workflow)
        self.assertIn('default: true', workflow)
        self.assertIn("-RequireLicense", workflow)
        self.assertIn("https://buymeacoffee.com/myriskdashk", workflow)
        self.assertIn("actions/upload-artifact", workflow)
        self.assertIn("release/*.exe", workflow)
        self.assertIn("release/*.zip", workflow)

    def test_publishing_checklist_includes_manual_github_release_steps(self) -> None:
        checklist = (ROOT / "docs" / "PUBLISHING_CHECKLIST.md").read_text(encoding="utf-8")

        self.assertIn("git push -u origin main", checklist)
        self.assertIn("git tag v0.1.0", checklist)
        self.assertIn("release\\DCS-AI-Copilot-Setup-0.1.0.exe", checklist)
        self.assertIn("release\\DCS-AI-Copilot-portable-0.1.0.zip", checklist)
        self.assertIn("-RequireInstaller -RequireLicense", checklist)
        self.assertIn("Prepare-GitHub-Release.ps1", checklist)
        self.assertIn("Prepare-Local-Git-Repository.ps1", checklist)
        self.assertIn("docs/LICENSE_HELP.md", checklist)
        self.assertIn("--license-help", checklist)
        self.assertIn("MIT `LICENSE`", checklist)
        self.assertIn("https://buymeacoffee.com/myriskdashk", checklist)
        self.assertIn("Test-Release-Smoke.ps1", checklist)
        self.assertIn("without launching interactive setup", checklist)

    def test_portable_installer_scripts_are_user_scoped(self) -> None:
        install_script = (ROOT / "packaging" / "windows" / "Install-DCS-AI-Copilot.ps1").read_text(encoding="utf-8")
        uninstall_script = (ROOT / "packaging" / "windows" / "Uninstall-DCS-AI-Copilot.ps1").read_text(encoding="utf-8")

        self.assertIn("$env:LOCALAPPDATA\\Programs\\DCS AI Copilot", install_script)
        self.assertIn("ArgumentList \"--setup\"", install_script)
        self.assertIn("NoLaunchSetup", install_script)
        self.assertIn("NoStartMenuShortcuts", install_script)
        self.assertIn("First-time setup was not started", install_script)
        self.assertIn("Audio Diagnostics.lnk", install_script)
        self.assertIn("--diagnose-audio", install_script)
        self.assertIn("License Help.lnk", install_script)
        self.assertIn("--license-help", install_script)
        self.assertIn("Release Check.lnk", install_script)
        self.assertIn("--release-check", install_script)
        self.assertIn("Refusing to uninstall outside", uninstall_script)
        self.assertIn("KeepUserConfig", uninstall_script)

    def test_release_smoke_script_validates_clean_portable_package(self) -> None:
        script = (ROOT / "packaging" / "windows" / "Test-Release-Smoke.ps1").read_text(encoding="utf-8")

        self.assertIn("DCS-AI-Copilot-portable-$Version.zip", script)
        self.assertIn("DCS-AI-Copilot-Setup-$Version.exe", script)
        self.assertIn("Expand-Archive", script)
        self.assertIn("Portable ZIP must not contain a real .env file", script)
        self.assertIn("--setup-help", script)
        self.assertIn("--release-check", script)
        self.assertIn("-NoLaunchSetup", script)
        self.assertIn("-NoStartMenuShortcuts", script)
        self.assertIn("Release smoke test passed", script)


if __name__ == "__main__":
    unittest.main()
