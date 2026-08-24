# DCS AI Copilot - User Setup Guide

This guide is for Windows users installing DCS AI Copilot for DCS World F/A-18C.

## What You Need

- Windows
- DCS World with F/A-18C
- OpenKneeboard installed
- DCS-BIOS installed if you want cockpit read-only data
- OpenAI API key with billing enabled
- Optional Gemini API key if you want Gemini speech-to-text fallback
- Microphone access in Windows
- Your VR platform/headset type, for example OpenXR/Pimax, OpenXR/other, SteamVR, Oculus, other or none

## First-Time Setup

If you downloaded the Windows installer:

1. Run `DCS-AI-Copilot-Setup-0.1.0.exe`.
2. Keep the default install folder unless you have a reason to change it:

```text
%LOCALAPPDATA%\Programs\DCS AI Copilot
```

3. Let the installer start the first-time setup wizard, or open it later from Start Menu:

```text
DCS AI Copilot > First-time Setup
```

If you downloaded the portable ZIP:

1. Extract the ZIP.
2. Either run `DCS-AI-Copilot.exe` directly, or install it for your Windows user:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-DCS-AI-Copilot.ps1
```

The installer script copies the app to:

```text
%LOCALAPPDATA%\Programs\DCS AI Copilot
```

It also creates Start Menu shortcuts for setup, doctor, joystick diagnostics and uninstall help.
It also includes `Setup Help`, which prints OpenKneeboard, PTT, backup and uninstall steps without changing your config.

If you are running from source, open PowerShell in the project folder:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
python main.py --setup
```

The setup wizard asks for:

- DCS World install path, for example `C:\Program Files\Eagle Dynamics\DCS World`
- DCS Saved Games path, for example `C:\Users\YourName\Saved Games\DCS.openbeta`
- VR platform/headset: `none`, `openxr-pimax`, `openxr-other`, `steamvr`, `oculus` or `other`
- OpenAI API key
- optional Gemini API key for fallback
- keyboard fallback PTT key, for example `f13`
- joystick backend, usually `winmm`
- joystick name, for example `WINWING F18 TAKEOFF PANEL 2`
- joystick button number, zero-based, for example `0`
- microphone input device, optional index or exact name from audio diagnostics
- optional Buy Me a Coffee URL

The wizard writes:

- `config.ini`
- `.env`

Your API key is stored in `.env`, not in `config.ini`.
Your VR platform is stored in `config.ini` only so help and doctor output can use the right wording. AI Copilot does not change OpenXR, SteamVR, Oculus, PimaxXR, QuadViews, Pimax Play or DCS graphics settings.

If you configure the API keys manually instead, copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`. Fill in `GEMINI_API_KEY` only if you want Gemini fallback. Do not share or commit the real `.env` file.

After writing the files, the wizard keeps helping until you answer that setup is satisfactory. It can show OpenKneeboard steps, PTT diagnostic steps, run doctor again, or help you start a DCS Saved Games backup.

To see the same post-install help later without rewriting config:

```powershell
python main.py --setup-help
```

For an installed app, use Start Menu:

```text
DCS AI Copilot > Setup Help
```

## Check The Installation

After setup, run:

```powershell
python main.py --doctor
```

For an installed app, use Start Menu:

```text
DCS AI Copilot > Check Installation
```

The doctor report checks:

- config file
- OpenAI API key
- Python packages
- DCS-BIOS reference folder
- OpenKneeboard install hints
- DCS World install path
- VR platform/headset choice
- microphone/input device
- dashboard port `127.0.0.1:8765`

If a line says `FAIL`, follow the `Fix:` line below it. If a line says `WARN`, the app may still run, but the feature may need manual setup.

## Start The App

```powershell
python main.py
```

For an installed app, use Start Menu:

```text
DCS AI Copilot > DCS AI Copilot
```

The dashboard URL is:

```text
http://127.0.0.1:8765
```

## OpenKneeboard Setup

1. Open OpenKneeboard.
2. Add a Web Dashboard page.
3. Use this URL:

```text
http://127.0.0.1:8765
```

4. Keep DCS AI Copilot running while using DCS.

## PTT Setup

To diagnose microphones/audio inputs:

```powershell
python main.py --diagnose-audio
```

For an installed app, use Start Menu:

```text
DCS AI Copilot > Audio Diagnostics
```

If Windows default microphone is not the mic you want, edit `config.ini`:

```ini
[voice]
input_device = 2
```

You can also use the exact device name printed by diagnostics.

To diagnose joystick buttons:

```powershell
python main.py --diagnose-joysticks
```

Press and release your desired PTT button.

For Windows Button 1, pygame/WinMM usually reports zero-based button:

```text
button=0
```

If needed, edit `config.ini`:

```ini
[voice]
ptt_mode = joystick
joystick_backend = winmm
joystick_name = WINWING F18 TAKEOFF PANEL 2
joystick_button = 0
joystick_winmm_device_id = auto
keyboard_ptt_key = f13
```

If auto-detection picks the wrong device, run joystick diagnostics and set `joystick_winmm_device_id` to the id printed for your panel.

The first-time setup wizard can also show these PTT steps again if you answer `no` when asked whether setup is satisfactory.

## What To Say

Coordinates:

```text
target north 4215 decimal 732 east 04138 decimal 219 elevation 428 feet
```

Notes:

```text
note tanker tacan 12 x fuel 4200
note attack heading 270 push time 15
anteckna bingo fuel 3500
```

## Speech-To-Text Providers

Default behavior:

```ini
[voice]
transcription_provider = openai
transcription_fallback_provider = gemini
transcription_model = gpt-4o-mini-transcribe
gemini_transcription_model = gemini-2.5-flash
```

OpenAI is tried first. Gemini is tried only if OpenAI fails and `GEMINI_API_KEY` is present in `.env`.

To disable Gemini fallback:

```ini
[voice]
transcription_fallback_provider =
```

To use Gemini as primary provider:

```ini
[voice]
transcription_provider = gemini
transcription_fallback_provider = openai
```

No local LLM, Ollama or GPU inference is used.

## API Usage And Cost

One released PTT recording normally creates one OpenAI transcription request. If OpenAI fails and Gemini fallback is enabled, the same recording may also create one Gemini request.

Cost is provider/model/usage based, not a fixed app fee per button press. For speech-to-text, the amount of audio and the selected model matter.

Check usage and spending here:

- OpenAI Platform usage/billing dashboard
- OpenAI Usage and Costs API
- Google AI Studio billing/usage
- Google Cloud Billing reports for the Gemini API project

Set provider-side spend limits or alerts before long multiplayer sessions.

## DCS Backup

To back up DCS Saved Games to another disk:

```powershell
python main.py --backup-dcs E:\DCS-Backups
```

To override the source folder:

```powershell
python main.py --backup-dcs E:\DCS-Backups --dcs-saved-games "C:\Users\YourName\Saved Games\DCS.openbeta"
```

The backup skips cache-heavy folders such as `fxo`, `metashaders`, logs and track files.

## Uninstall Help

For this development build:

```powershell
python main.py --uninstall-help
```

Installed release builds can be removed from Windows Apps & features or from Start Menu:

```text
DCS AI Copilot > Uninstall DCS AI Copilot
```
Portable ZIP installs made with `Install-DCS-AI-Copilot.ps1` can be removed with:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\DCS AI Copilot\Uninstall-DCS-AI-Copilot.ps1"
```

## Troubleshooting

If the dashboard does not open:

- Check that the app is running.
- Make sure no old Python process is already using port `8765`.

If PTT does not record:

- Run `python main.py --doctor`.
- Run `python main.py --diagnose-audio`.
- Run `python main.py --diagnose-joysticks`.
- Verify the configured device id and button number.
- Check Windows microphone privacy permissions.

If transcription fails:

- Check `.env` contains `OPENAI_API_KEY=...`.
- If Gemini fallback is enabled, check `.env` contains `GEMINI_API_KEY=...`.
- Check OpenAI Platform billing and usage.
- Check Gemini API billing/usage if fallback is being used.

If coordinates do not parse:

- Check `LAST TRANSCRIPT`.
- Say coordinates in a compact format:

```text
target north 4215 decimal 732 east 04138 decimal 219 elevation 428 feet
```
