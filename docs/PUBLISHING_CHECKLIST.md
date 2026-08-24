# Publishing Checklist

Use this before publishing DCS AI Copilot on GitHub.

## Required Before Public Release

- Confirm the MIT license text exists in `LICENSE`.
- Add your real Buy Me a Coffee URL through `config.ini` or the build script.
- Test a clean install on a Windows machine that does not have the development folder.
- Confirm `.env` is not included in the installer or GitHub repository.
- Confirm `.env.example` is included and contains placeholders only.
- Confirm the app does not modify DCS graphics, OpenXR, PimaxXR, QuadViews or Pimax Play settings.
- Confirm the app sends no DCS-BIOS cockpit commands.
- Confirm multiplayer safety statement is visible in README/release notes.

## License Helper

Review `docs/LICENSE_HELP.md` or run:

```powershell
python main.py --license-help
```

DCS AI Copilot currently uses the MIT License in `LICENSE`. The helper explains the exact license file required by release-check.

## Build Portable App

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
.\packaging\windows\build_windows.ps1 -Version "0.1.0" -BuyMeACoffeeUrl "https://buymeacoffee.com/myriskdashk"
```

Output:

```text
dist\DCS-AI-Copilot
release\DCS-AI-Copilot-Setup-0.1.0.exe
release\DCS-AI-Copilot-portable-0.1.0.zip
release\RELEASE_NOTES-0.1.0.md
packaging\windows\DCS-AI-Copilot.generated.iss
```

## Build Installer

1. Install Inno Setup.
2. Run `packaging\windows\build_windows.ps1`.
3. The script generates:

```text
packaging\windows\DCS-AI-Copilot.generated.iss
```

4. If Inno Setup is installed, the script compiles the installer automatically.
5. If not, open the generated `.iss` file in Inno Setup and compile it manually.

For CI or final release builds, require the installer so the build fails if Inno Setup is missing:

```powershell
.\packaging\windows\build_windows.ps1 -Version "0.1.0" -RequireInstaller
```

For the final public build, also require your real `LICENSE` file:

```powershell
.\packaging\windows\build_windows.ps1 -Version "0.1.0" -BuyMeACoffeeUrl "https://buymeacoffee.com/myriskdashk" -RequireInstaller -RequireLicense
```

The installer should run:

```text
DCS-AI-Copilot.exe --setup
```

after installation.

## Release Readiness Check

Run this before commit/tag/release upload:

```powershell
python main.py --release-check --release-version 0.1.0
```

Or from the built app:

```powershell
.\dist\DCS-AI-Copilot\DCS-AI-Copilot.exe --release-check --release-version 0.1.0
```

The check fails if required public release inputs are missing, including:

- final `LICENSE`
- real Buy Me a Coffee URL
- installer, portable ZIP and release notes
- `.env.example` placeholders
- no `.env` inside the portable ZIP
- README/release-note safety statements

## Release Smoke Test

After the final build, test the release ZIP and the per-user installer script from a clean temporary folder:

```powershell
.\packaging\windows\Test-Release-Smoke.ps1 -Version "0.1.0"
```

The smoke test verifies that the ZIP does not contain `.env`, public helper files are included, the built executable can show help/release-check output, and the portable install/uninstall scripts work without launching interactive setup.

## Final Release Helper

After your real Buy Me a Coffee URL exists, this helper runs tests, builds the installer/ZIP, requires `LICENSE`, runs release-check, then prints the manual GitHub commands:

```powershell
.\packaging\windows\Prepare-GitHub-Release.ps1 -Version "0.1.0" -BuyMeACoffeeUrl "https://buymeacoffee.com/myriskdashk" -GitHubUser "YOUR_GITHUB_USER"
```

It does not run `git push` or create a GitHub release automatically.

## GitHub Release Contents

- Installer `.exe`
- Portable `.zip`
- `release/RELEASE_NOTES-*.md`
- README
- `docs/USER_SETUP_GUIDE.md`
- `.env.example`
- `LICENSE`
- Known limitations

## Initialize And Push GitHub Repository

Do this only after the final MIT `LICENSE` file exists, your real Buy Me a Coffee URL is configured, and release-check is green.

Prepare the local commit and tag. This command sets Git identity only for this repository:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
.\packaging\windows\Prepare-Local-Git-Repository.ps1 -Version "0.1.0" -GitUserName "YOUR_GIT_NAME" -GitUserEmail "YOUR_GIT_EMAIL" -GitHubUser "YOUR_GITHUB_USER"
```

The script refuses to commit `.env`, `.env.*`, `release/`, `dist/`, `build/`, `build-meta/` or `.build-venv/`.
It also creates the version tag, equivalent to `git tag v0.1.0`.

Create an empty GitHub repository named `dcs-ai-copilot`, then push:

```powershell
git push -u origin main
git push origin v0.1.0
```

Then create a GitHub Release for `v0.1.0` and upload:

```text
release\DCS-AI-Copilot-Setup-0.1.0.exe
release\DCS-AI-Copilot-portable-0.1.0.zip
release\RELEASE_NOTES-0.1.0.md
```

## GitHub Actions

Manual Windows builds can be started from:

```text
.github/workflows/windows-build.yml
```

The workflow runs tests, builds the portable app, and uploads release artifacts.
It installs Inno Setup in the Windows runner and uses `-RequireInstaller`, so missing installer output fails the workflow instead of silently publishing only a ZIP.
For final public release workflow runs, set `require_license` to `true`.

Automatic GitHub releases are created when a version tag is pushed:

```powershell
git tag v0.1.1
git push origin main
git push origin v0.1.1
```

Repository or organization Actions permissions must allow read/write access for `GITHUB_TOKEN`.

## Known Limitations For Early Release

- DCS-BIOS is read-only.
- No cockpit commands are sent.
- No SRS/Discord integration yet.
- Speech-to-text requires an OpenAI API key as primary provider.
- Gemini can be configured as cloud fallback for speech-to-text.
