from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dcs_ai_copilot.setup.maintenance import backup_dcs_saved_games
from dcs_ai_copilot.setup.dcs_bios_help import format_dcs_bios_setup_help, inspect_dcs_bios_setup


DEFAULT_WEB_URL = "http://127.0.0.1:8765"
DEFAULT_BUY_ME_A_COFFEE_URL = ""


@dataclass(frozen=True)
class SetupAnswers:
    dcs_install_path: str
    dcs_saved_games_path: str
    vr_platform: str
    openai_api_key: str
    gemini_api_key: str
    keyboard_ptt_key: str
    joystick_backend: str
    joystick_name: str
    joystick_button: str
    joystick_winmm_device_id: str
    input_device: str
    buy_me_a_coffee_url: str = DEFAULT_BUY_ME_A_COFFEE_URL


def run_setup_wizard(
    project_root: Path,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> int:
    print_func("DCS AI Copilot setup")
    print_func("This wizard writes config.ini and .env for this installation.")
    print_func("")

    default_saved_games = _default_saved_games_path()
    default_dcs_install = _default_dcs_install_path()
    answers = SetupAnswers(
        dcs_install_path=_ask(
            input_func,
            "DCS World install path, optional",
            default_dcs_install,
        ),
        dcs_saved_games_path=_ask(
            input_func,
            "DCS Saved Games path",
            default_saved_games,
        ),
        vr_platform=_ask_choice(
            input_func,
            "VR platform/headset",
            choices=("none", "openxr-pimax", "openxr-other", "steamvr", "oculus", "other"),
            default="openxr-other",
        ),
        openai_api_key=_ask_secret(input_func, "OpenAI API key"),
        gemini_api_key=_ask_secret(input_func, "Gemini API key, optional fallback"),
        keyboard_ptt_key=_ask(input_func, "Keyboard fallback PTT key", "f13"),
        joystick_backend=_ask_choice(
            input_func,
            "Joystick backend",
            choices=("winmm", "pygame", "auto"),
            default="winmm",
        ),
        joystick_name=_ask(
            input_func,
            "Joystick device name",
            "WINWING F18 TAKEOFF PANEL 2",
        ),
        joystick_button=_ask(input_func, "Joystick button number, zero-based", "0"),
        joystick_winmm_device_id=_ask(input_func, "WinMM device id", "auto"),
        input_device=_ask(input_func, "Microphone input device, optional index/name", ""),
        buy_me_a_coffee_url=_ask(
            input_func,
            "Buy Me a Coffee URL, optional",
            DEFAULT_BUY_ME_A_COFFEE_URL,
        ),
    )

    write_setup_files(project_root, answers)
    print_func("")
    print_func("Setup complete.")
    from dcs_ai_copilot.setup.doctor import format_doctor_report, run_doctor

    print_func("")
    print_func(format_doctor_report(run_doctor(project_root / "config.ini")))
    print_func("")
    print_func(f"OpenKneeboard Web Dashboard URL: {DEFAULT_WEB_URL}")
    print_func(_next_steps_text())
    _run_onboarding_loop(project_root, answers, input_func, print_func)
    return 0


def write_setup_files(project_root: Path, answers: SetupAnswers) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    config = build_config(answers)
    with (project_root / "config.ini").open("w", encoding="utf-8") as file:
        config.write(file)
    _write_env_file(project_root / ".env", answers.openai_api_key, answers.gemini_api_key)


def build_config(answers: SetupAnswers) -> configparser.ConfigParser:
    dcs_saved_games = Path(answers.dcs_saved_games_path).expanduser()
    reference_dir = dcs_saved_games / "Scripts" / "DCS-BIOS" / "doc" / "json"

    config = configparser.ConfigParser()
    config["paths"] = {
        "kneeboard_file": "kneeboard.html",
        "log_file": "logs/dcs-ai-copilot.log",
    }
    config["web"] = {
        "host": "127.0.0.1",
        "port": "8765",
    }
    config["openkneeboard"] = {
        "dashboard_url": DEFAULT_WEB_URL,
    }
    config["dcs"] = {
        "install_path": answers.dcs_install_path.strip(),
        "saved_games_path": str(dcs_saved_games),
    }
    config["vr"] = {
        "platform": answers.vr_platform.strip() or "openxr-other",
        "managed_by_ai_copilot": "false",
    }
    config["dcs_bios"] = {
        "enabled": "true",
        "multicast_group": "239.255.50.10",
        "port": "5010",
        "reference_dir": str(reference_dir),
    }
    config["voice"] = {
        "enabled": "true",
        "ptt_mode": "joystick",
        "keyboard_ptt_key": answers.keyboard_ptt_key.strip() or "f13",
        "joystick_backend": answers.joystick_backend.strip() or "winmm",
        "joystick_name": answers.joystick_name.strip(),
        "joystick_button": answers.joystick_button.strip() or "0",
        "joystick_winmm_device_id": answers.joystick_winmm_device_id.strip() or "auto",
        "joystick_poll_interval_seconds": "0.01",
        "input_device": answers.input_device.strip(),
        "sample_rate": "16000",
        "channels": "1",
        "max_record_seconds": "90",
        "transcription_provider": "openai",
        "transcription_fallback_provider": "gemini" if answers.gemini_api_key.strip() else "",
        "transcription_model": "gpt-4o-mini-transcribe",
        "gemini_transcription_model": "gemini-2.5-flash",
        "env_file": ".env",
    }
    config["donation"] = {
        "buy_me_a_coffee_url": answers.buy_me_a_coffee_url.strip(),
    }
    return config


def _write_env_file(path: Path, openai_api_key: str, gemini_api_key: str) -> None:
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    secrets = {
        "OPENAI_API_KEY": openai_api_key.strip(),
        "GEMINI_API_KEY": gemini_api_key.strip(),
    }
    replaced = {key: False for key in secrets}
    output_lines: list[str] = []
    for line in lines:
        key = line.partition("=")[0].strip()
        if key in secrets:
            output_lines.append(f"{key}={secrets[key]}")
            replaced[key] = True
            continue
        output_lines.append(line)
    for key, was_replaced in replaced.items():
        if not was_replaced:
            output_lines.append(f"{key}={secrets[key]}")
    path.write_text("\n".join(output_lines).strip() + "\n", encoding="utf-8")


def _ask(input_func: Callable[[str], str], label: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    value = input_func(f"{label}{suffix}: ").strip()
    return value or default


def _ask_choice(
    input_func: Callable[[str], str],
    label: str,
    choices: tuple[str, ...],
    default: str,
) -> str:
    while True:
        value = _ask(input_func, f"{label} ({'/'.join(choices)})", default).lower()
        if value in choices:
            return value
        print(f"Please enter one of: {', '.join(choices)}")


def _ask_secret(input_func: Callable[[str], str], label: str) -> str:
    value = input_func(f"{label}: ").strip()
    return value


def _default_saved_games_path() -> str:
    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    openbeta = user_profile / "Saved Games" / "DCS.openbeta"
    stable = user_profile / "Saved Games" / "DCS"
    if openbeta.exists():
        return str(openbeta)
    return str(stable)


def _default_dcs_install_path() -> str:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Eagle Dynamics" / "DCS World OpenBeta",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Eagle Dynamics" / "DCS World",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps" / "common" / "DCSWorld",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam" / "steamapps" / "common" / "DCSWorld",
    ]
    for candidate in candidates:
        if _looks_like_dcs_install(candidate):
            return str(candidate)
    return ""


def _looks_like_dcs_install(path: Path) -> bool:
    return (path / "bin" / "DCS.exe").exists() or (path / "DCS.exe").exists()


def _run_onboarding_loop(
    project_root: Path,
    answers: SetupAnswers,
    input_func: Callable[[str], str],
    print_func: Callable[[str], None],
) -> None:
    while True:
        satisfied = _ask_choice(
            input_func,
            "Are you satisfied with setup so far?",
            choices=("yes", "no"),
            default="yes",
        )
        if satisfied == "yes":
            print_func("Good. Start the app when ready and keep this guide nearby.")
            return

        print_func("")
        print_func("Setup help menu")
        print_func("1. Show OpenKneeboard Web Dashboard steps")
        print_func("2. Show PTT/joystick diagnostic steps")
        print_func("3. Show DCS-BIOS setup/repair steps")
        print_func("4. Run doctor again")
        print_func("5. Back up DCS Saved Games now")
        print_func("6. Finish setup")
        choice = _ask(input_func, "Choose", "3")
        print_func("")

        if choice == "1":
            print_func(_openkneeboard_steps_text())
        elif choice == "2":
            print_func(_ptt_steps_text())
        elif choice == "3":
            print_func(format_dcs_bios_setup_help(inspect_dcs_bios_setup(Path(answers.dcs_saved_games_path))))
        elif choice == "4":
            from dcs_ai_copilot.setup.doctor import format_doctor_report, run_doctor

            print_func(format_doctor_report(run_doctor(project_root / "config.ini")))
        elif choice == "5":
            destination = _ask(input_func, "Backup destination folder", "")
            if not destination:
                print_func("Backup skipped because no destination was entered.")
            else:
                try:
                    backup_path = backup_dcs_saved_games(
                        Path(answers.dcs_saved_games_path),
                        Path(destination),
                    )
                except Exception as exc:
                    print_func(f"Backup failed: {exc}")
                else:
                    print_func(f"Backup created: {backup_path}")
        elif choice == "6":
            print_func("Setup finished.")
            return
        else:
            print_func("Unknown choice.")
        print_func("")


def _next_steps_text() -> str:
    return "\n".join(
        [
            "Next steps:",
            "1. Start AI Copilot: DCS-AI-Copilot.exe, or python main.py from source.",
            f"2. Add OpenKneeboard Web Dashboard URL: {DEFAULT_WEB_URL}",
            "3. If PTT does not respond, run: DCS-AI-Copilot.exe --diagnose-joysticks",
            "4. If the microphone is wrong, run: DCS-AI-Copilot.exe --diagnose-audio",
            "5. Gemini fallback is optional. Add GEMINI_API_KEY in .env if you want it.",
            "6. If something is unclear, run: DCS-AI-Copilot.exe --doctor",
            "7. For DCS-BIOS install/repair steps, run: DCS-AI-Copilot.exe --dcs-bios-help",
            "8. VR platform is stored for help text only; AI Copilot does not change VR settings.",
        ]
    )


def setup_help_text() -> str:
    return "\n\n".join(
        [
            "DCS AI Copilot setup help",
            _next_steps_text(),
            _openkneeboard_steps_text(),
            _ptt_steps_text(),
            format_dcs_bios_setup_help(inspect_dcs_bios_setup()),
            _backup_steps_text(),
            _uninstall_steps_text(),
        ]
    )


def _openkneeboard_steps_text() -> str:
    return "\n".join(
        [
            "OpenKneeboard setup:",
            "1. Open OpenKneeboard.",
            "2. Add a Web Dashboard tab/page.",
            f"3. Use URL: {DEFAULT_WEB_URL}",
            "4. Start DCS AI Copilot before or during DCS.",
            "5. The page updates automatically while AI Copilot is running.",
        ]
    )


def _ptt_steps_text() -> str:
    return "\n".join(
        [
            "PTT setup:",
            "1. Run: DCS-AI-Copilot.exe --diagnose-joysticks",
            "2. Press and release the desired physical joystick/input button.",
            "3. Note the reported device/backend and zero-based button number.",
            "4. Re-run setup or edit config.ini if the configured button is wrong.",
            "5. Run: DCS-AI-Copilot.exe --diagnose-audio",
            "6. If the default microphone is wrong, set [voice] input_device to the listed index or exact name.",
            "7. Keyboard fallback is configured separately, usually F13.",
        ]
    )


def _backup_steps_text() -> str:
    return "\n".join(
        [
            "DCS backup:",
            "1. Choose a backup destination on another disk if possible.",
            "2. Run: DCS-AI-Copilot.exe --backup-dcs E:\\DCS-Backups",
            "3. From source, run: python main.py --backup-dcs E:\\DCS-Backups",
            "4. To override the source, add: --dcs-saved-games \"C:\\Users\\YourName\\Saved Games\\DCS.openbeta\"",
            "5. Cache-heavy folders such as fxo, metashaders, logs and track files are skipped.",
        ]
    )


def _uninstall_steps_text() -> str:
    return "\n".join(
        [
            "Uninstall:",
            "1. Installed app: use Windows Apps & features or Start Menu > DCS AI Copilot > Uninstall DCS AI Copilot.",
            "2. Portable install: run Uninstall-DCS-AI-Copilot.ps1 from the install folder.",
            "3. User config can be kept or removed by the uninstall script.",
            "4. DCS, OpenKneeboard, OpenXR, PimaxXR, QuadViews and graphics settings are not changed by uninstall.",
        ]
    )
