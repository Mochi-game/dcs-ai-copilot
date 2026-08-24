from __future__ import annotations

import configparser
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ReleaseCheckResult:
    name: str
    status: str
    detail: str
    action: str = ""


def default_dcs_saved_games_path() -> Path:
    home = Path.home()
    openbeta = home / "Saved Games" / "DCS.openbeta"
    stable = home / "Saved Games" / "DCS"
    if openbeta.exists():
        return openbeta
    return stable


def backup_dcs_saved_games(source: Path, destination_root: Path) -> Path:
    source = source.expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"DCS Saved Games path does not exist: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"DCS Saved Games path is not a directory: {source}")

    destination_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = destination_root / f"{source.name}-backup-{timestamp}"
    shutil.copytree(
        source,
        backup_dir,
        ignore=shutil.ignore_patterns(
            "fxo",
            "metashaders",
            "metashaders2",
            "Logs",
            "*.track",
        ),
    )
    return backup_dir


def uninstall_help(project_root: Path) -> str:
    project_root = project_root.resolve()
    return "\n".join(
        [
            "DCS AI Copilot uninstall help",
            "",
            "This project does not install files into DCS or Windows system folders yet.",
            "To remove this development copy:",
            "1. Stop AI Copilot.",
            f"2. Delete project folder: {project_root}",
            "3. Delete desktop shortcuts if you created them.",
            "4. Leave DCS-BIOS and OpenKneeboard installed if you use them elsewhere.",
            "",
            "No DCS, OpenXR, PimaxXR, QuadViews or graphics settings are modified by this app.",
        ]
    )


def license_help(project_root: Path) -> str:
    project_root = project_root.resolve()
    return "\n".join(
        [
            "DCS AI Copilot license help",
            "",
            "DCS AI Copilot currently uses the MIT License.",
            "A public GitHub release needs this real LICENSE file in the project root:",
            str(project_root / "LICENSE"),
            "",
            "Common license context:",
            "- MIT: permissive, short, lets others use and modify the code with attribution.",
            "- Apache-2.0: permissive, includes explicit patent terms.",
            "- GPL-3.0: copyleft, requires distributed derivatives to stay open source.",
            "- Custom/personal license: use this only if standard open source terms are not what you want.",
            "",
            "Steps before publishing:",
            "1. Confirm LICENSE contains the MIT License text.",
            "2. Confirm the copyright line is correct for the release owner.",
            "3. Remove or leave LICENSE.template.md only as a helper; do not publish it as the final license.",
            "4. Add your real Buy Me a Coffee URL before the final public build.",
            "5. Run: python main.py --release-check --release-version 0.1.0",
            "",
            "Helpful reference:",
            "https://choosealicense.com/",
        ]
    )


def run_release_check(project_root: Path, version: str = "0.1.0") -> list[ReleaseCheckResult]:
    project_root = project_root.resolve()
    release_root = project_root / "release"
    portable_zip = release_root / f"DCS-AI-Copilot-portable-{version}.zip"
    installer = release_root / f"DCS-AI-Copilot-Setup-{version}.exe"
    release_notes = release_root / f"RELEASE_NOTES-{version}.md"

    return [
        _check_license(project_root),
        _check_buy_me_a_coffee(project_root / "config.ini"),
        _check_env_example(project_root / ".env.example"),
        _check_gitignore(project_root / ".gitignore"),
        _check_release_file("Windows installer", installer),
        _check_release_file("Portable ZIP", portable_zip),
        _check_release_file("Release notes", release_notes),
        _check_portable_zip(portable_zip),
        _check_readme_safety(project_root / "README.md"),
        _check_release_notes(release_notes),
    ]


def format_release_check_report(results: list[ReleaseCheckResult]) -> str:
    lines = ["DCS AI Copilot release check", ""]
    for result in results:
        lines.append(f"[{result.status}] {result.name}: {result.detail}")
        if result.action:
            lines.append(f"      Fix: {result.action}")
    lines.append("")
    if any(result.status == "FAIL" for result in results):
        lines.append("Release is not ready yet.")
    else:
        lines.append("No blocking release issues found.")
    return "\n".join(lines)


def release_check_exit_code(results: list[ReleaseCheckResult]) -> int:
    return 1 if any(result.status == "FAIL" for result in results) else 0


def _check_license(project_root: Path) -> ReleaseCheckResult:
    license_path = project_root / "LICENSE"
    if license_path.exists():
        text = license_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            return ReleaseCheckResult(
                "LICENSE",
                "FAIL",
                "LICENSE exists but is empty.",
                "Add the full final license text.",
            )
        template_markers = [
            "Choose and replace this file",
            "YEAR AUTHOR",
            "Copyright (c) YEAR",
        ]
        if any(marker in text for marker in template_markers):
            return ReleaseCheckResult(
                "LICENSE",
                "FAIL",
                "LICENSE still looks like a template.",
                "Replace template placeholders with the final license text.",
            )
        return ReleaseCheckResult("LICENSE", "OK", str(license_path))
    return ReleaseCheckResult(
        "LICENSE",
        "FAIL",
        "Final LICENSE file is missing.",
        "Choose your license, create LICENSE, then rebuild with -RequireLicense.",
    )


def _check_buy_me_a_coffee(config_file: Path) -> ReleaseCheckResult:
    if not config_file.exists():
        return ReleaseCheckResult(
            "Buy Me a Coffee URL",
            "FAIL",
            "config.ini is missing.",
            "Run setup or restore config.ini before building the release.",
        )
    parser = configparser.ConfigParser()
    parser.read(config_file, encoding="utf-8")
    url = parser.get("donation", "buy_me_a_coffee_url", fallback="").strip()
    if url.startswith("https://buymeacoffee.com/"):
        return ReleaseCheckResult("Buy Me a Coffee URL", "OK", url)
    return ReleaseCheckResult(
        "Buy Me a Coffee URL",
        "FAIL",
        url or "not configured",
        "Set [donation] buy_me_a_coffee_url or build with -BuyMeACoffeeUrl.",
    )


def _check_env_example(path: Path) -> ReleaseCheckResult:
    if not path.exists():
        return ReleaseCheckResult(".env.example", "FAIL", "Missing.", "Add .env.example with placeholder keys.")
    text = path.read_text(encoding="utf-8", errors="ignore")
    required = ["OPENAI_API_KEY=", "GEMINI_API_KEY="]
    missing = [item for item in required if item not in text]
    if missing:
        return ReleaseCheckResult(
            ".env.example",
            "FAIL",
            f"Missing placeholders: {', '.join(missing)}",
            "Add placeholder keys without real secrets.",
        )
    suspicious_markers = ["sk-", "AIza"]
    if any(marker in text for marker in suspicious_markers):
        return ReleaseCheckResult(
            ".env.example",
            "FAIL",
            "Looks like it may contain a real API key.",
            "Replace real keys with empty placeholders.",
        )
    return ReleaseCheckResult(".env.example", "OK", "Contains placeholders only.")


def _check_gitignore(path: Path) -> ReleaseCheckResult:
    if not path.exists():
        return ReleaseCheckResult(".gitignore", "FAIL", "Missing.", "Add .gitignore before publishing.")
    text = path.read_text(encoding="utf-8", errors="ignore")
    if ".env" in text and "!.env.example" in text:
        return ReleaseCheckResult(".gitignore", "OK", ".env ignored and .env.example allowed.")
    return ReleaseCheckResult(
        ".gitignore",
        "FAIL",
        "Secret env file rules are missing.",
        "Ignore .env and explicitly allow .env.example.",
    )


def _check_release_file(name: str, path: Path) -> ReleaseCheckResult:
    if path.exists() and path.stat().st_size > 0:
        return ReleaseCheckResult(name, "OK", str(path))
    return ReleaseCheckResult(
        name,
        "FAIL",
        f"Missing or empty: {path}",
        "Run packaging/windows/build_windows.ps1 -Version 0.1.0 -RequireInstaller.",
    )


def _check_portable_zip(path: Path) -> ReleaseCheckResult:
    if not path.exists():
        return ReleaseCheckResult("Portable ZIP contents", "FAIL", "ZIP missing.", "Build release artifacts first.")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            has_env = any(name.endswith(".env") for name in names)
            required = {
                "DCS-AI-Copilot.exe",
                "LICENSE",
                ".env.example",
                "README.md",
                "docs/LICENSE_HELP.md",
                "docs/USER_SETUP_GUIDE.md",
                "Install-DCS-AI-Copilot.ps1",
                "Uninstall-DCS-AI-Copilot.ps1",
                "Prepare-GitHub-Release.ps1",
                "Prepare-Local-Git-Repository.ps1",
                "Test-Release-Smoke.ps1",
            }
    except zipfile.BadZipFile:
        return ReleaseCheckResult("Portable ZIP contents", "FAIL", "ZIP is invalid.", "Rebuild the portable ZIP.")
    missing = sorted(required - names)
    if has_env:
        return ReleaseCheckResult(
            "Portable ZIP contents",
            "FAIL",
            "ZIP contains a real .env file.",
            "Remove .env from build artifacts and rebuild.",
        )
    if missing:
        return ReleaseCheckResult(
            "Portable ZIP contents",
            "FAIL",
            f"Missing: {', '.join(missing)}",
            "Rebuild the portable ZIP after restoring required files.",
        )
    return ReleaseCheckResult("Portable ZIP contents", "OK", "Required public files are present; .env is absent.")


def _check_readme_safety(path: Path) -> ReleaseCheckResult:
    if not path.exists():
        return ReleaseCheckResult("README safety", "FAIL", "README.md missing.", "Restore README.md.")
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    required = [
        "dcs-bios",
        "read-only",
        "no cockpit commands",
        "no hidden multiplayer",
        "no local ai",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        return ReleaseCheckResult(
            "README safety",
            "FAIL",
            f"Missing safety text: {', '.join(missing)}",
            "Make multiplayer/read-only/no-local-AI safety visible in README.",
        )
    return ReleaseCheckResult("README safety", "OK", "Safety statements are visible.")


def _check_release_notes(path: Path) -> ReleaseCheckResult:
    if not path.exists():
        return ReleaseCheckResult("Release notes safety", "FAIL", "Release notes missing.", "Rebuild release notes.")
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "gemini fallback is planned" in text:
        return ReleaseCheckResult(
            "Release notes safety",
            "FAIL",
            "Release notes still say Gemini fallback is planned.",
            "Regenerate release notes after the Gemini implementation.",
        )
    required = ["read-only", "no cockpit commands", "no hidden multiplayer"]
    missing = [item for item in required if item not in text]
    if missing:
        return ReleaseCheckResult(
            "Release notes safety",
            "FAIL",
            f"Missing safety text: {', '.join(missing)}",
            "Regenerate or edit release notes before publishing.",
        )
    return ReleaseCheckResult("Release notes safety", "OK", "Safety statements are visible.")
