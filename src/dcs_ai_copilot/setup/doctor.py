from __future__ import annotations

import importlib.util
import os
import socket
from dataclasses import dataclass
from pathlib import Path

from dcs_ai_copilot.config import AppConfig, load_config
from dcs_ai_copilot.dcs_bios.discovery import find_reference_dirs
from dcs_ai_copilot.env import load_env_file
from dcs_ai_copilot.setup.dcs_bios_help import inspect_dcs_bios_setup
from dcs_ai_copilot.setup.wizard import DEFAULT_WEB_URL
from dcs_ai_copilot.voice.audio import list_audio_input_devices


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str
    action: str = ""


def run_doctor(config_file: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    if not config_file.exists():
        return [
            CheckResult(
                "Config",
                "FAIL",
                f"Missing config file: {config_file}",
                "Run setup first: DCS-AI-Copilot.exe --setup, or python main.py --setup from source.",
            )
        ]

    config = load_config(config_file)
    load_env_file(config.env_file)
    results.extend(_check_config(config))
    results.extend(_check_python_packages())
    results.extend(_check_openkneeboard())
    results.extend(_check_dashboard_port(config.web_host, config.web_port))
    return results


def format_doctor_report(results: list[CheckResult]) -> str:
    lines = ["DCS AI Copilot doctor", ""]
    for result in results:
        lines.append(f"[{result.status}] {result.name}: {result.detail}")
        if result.action:
            lines.append(f"      Fix: {result.action}")
    lines.append("")
    if all(result.status != "FAIL" for result in results):
        lines.append("No blocking issues found.")
    else:
        lines.append("One or more required setup items need attention.")
    return "\n".join(lines)


def _check_config(config: AppConfig) -> list[CheckResult]:
    results = [
        _check_openai_key(),
        _check_gemini_key(config.voice_transcription_fallback_provider),
        _check_dcs_install(config.dcs_install_path),
        _check_dcs_saved_games(config.dcs_saved_games_path),
        _check_vr_platform(config.vr_platform, config.vr_managed_by_ai_copilot),
        _check_audio_input_device(config.voice_input_device),
        _check_dcs_bios_reference(config.dcs_bios_reference_dir),
        _check_dcs_bios_export(config.dcs_saved_games_path),
        CheckResult(
            "OpenKneeboard URL",
            "OK",
            f"Use {DEFAULT_WEB_URL} in OpenKneeboard Web Dashboard.",
        ),
        CheckResult(
            "Web bind address",
            "OK" if config.web_host == "127.0.0.1" else "FAIL",
            config.web_host,
            "" if config.web_host == "127.0.0.1" else "Set [web] host = 127.0.0.1 in config.ini.",
        ),
    ]
    return results


def _check_openai_key() -> CheckResult:
    value = os.environ.get("OPENAI_API_KEY", "").strip()
    if value:
        return CheckResult("OpenAI API key", "OK", "OPENAI_API_KEY is present.")
    return CheckResult(
        "OpenAI API key",
        "FAIL",
        "OPENAI_API_KEY is missing.",
        "Run setup or add OPENAI_API_KEY=... to .env.",
    )


def _check_gemini_key(fallback_provider: str) -> CheckResult:
    if fallback_provider.strip().lower() != "gemini":
        return CheckResult("Gemini fallback API key", "OK", "Gemini fallback is disabled.")
    value = os.environ.get("GEMINI_API_KEY", "").strip()
    if value:
        return CheckResult("Gemini fallback API key", "OK", "GEMINI_API_KEY is present.")
    return CheckResult(
        "Gemini fallback API key",
        "WARN",
        "Gemini fallback is enabled but GEMINI_API_KEY is missing.",
        "Add GEMINI_API_KEY=... to .env or set [voice] transcription_fallback_provider empty.",
    )


def _check_path(name: str, path: Path | None, action: str, required: bool = True) -> CheckResult:
    if path and path.exists():
        return CheckResult(name, "OK", str(path))
    return CheckResult(name, "FAIL" if required else "WARN", str(path or "not configured"), action)


def _check_dcs_install(configured_dir: Path | None) -> CheckResult:
    if configured_dir and _looks_like_dcs_install(configured_dir):
        return CheckResult("DCS World install path", "OK", str(configured_dir))
    detail = str(configured_dir) if configured_dir else "not configured"
    return CheckResult(
        "DCS World install path",
        "WARN",
        detail,
        "Run setup and enter the DCS World install folder, for example C:\\Program Files\\Eagle Dynamics\\DCS World.",
    )


def _looks_like_dcs_install(path: Path) -> bool:
    return (path / "bin" / "DCS.exe").exists() or (path / "DCS.exe").exists()


def _check_dcs_saved_games(configured_dir: Path | None) -> CheckResult:
    if configured_dir and configured_dir.exists():
        return CheckResult("DCS Saved Games path", "OK", str(configured_dir))
    detail = str(configured_dir) if configured_dir else "not configured"
    return CheckResult(
        "DCS Saved Games path",
        "WARN",
        detail,
        "Run setup and enter your Saved Games DCS folder, for example C:\\Users\\YourName\\Saved Games\\DCS.openbeta.",
    )


def _check_vr_platform(platform: str, managed_by_ai_copilot: bool) -> CheckResult:
    normalized = platform.strip().lower() or "openxr-other"
    known = {"none", "openxr-pimax", "openxr-other", "steamvr", "oculus", "other"}
    if normalized not in known:
        return CheckResult(
            "VR platform",
            "WARN",
            platform,
            "Use setup and choose one of: none, openxr-pimax, openxr-other, steamvr, oculus, other.",
        )
    if managed_by_ai_copilot:
        return CheckResult(
            "VR settings",
            "FAIL",
            "managed_by_ai_copilot must be false.",
            "Set [vr] managed_by_ai_copilot = false. AI Copilot must not change VR settings.",
        )
    return CheckResult(
        "VR platform",
        "OK",
        f"{normalized}; AI Copilot stores this for help text only and does not change VR settings.",
    )


def _check_audio_input_device(configured_device: str) -> CheckResult:
    configured_device = configured_device.strip()
    if not configured_device:
        return CheckResult(
            "Microphone input device",
            "OK",
            "Using Windows/default sounddevice input.",
            "Run DCS-AI-Copilot.exe --diagnose-audio if the wrong microphone records.",
        )
    try:
        devices = list_audio_input_devices()
    except Exception as exc:
        return CheckResult(
            "Microphone input device",
            "WARN",
            f"Could not query audio devices: {exc}",
            "Run DCS-AI-Copilot.exe --diagnose-audio and check Windows microphone permissions.",
        )

    if _audio_device_matches(configured_device, devices):
        return CheckResult("Microphone input device", "OK", configured_device)
    return CheckResult(
        "Microphone input device",
        "WARN",
        configured_device,
        "Run DCS-AI-Copilot.exe --diagnose-audio, then set [voice] input_device to a listed index or exact name.",
    )


def _audio_device_matches(configured_device: str, devices) -> bool:
    configured_lower = configured_device.lower()
    try:
        configured_index = int(configured_device)
    except ValueError:
        configured_index = None
    for device in devices:
        if configured_index is not None and device.index == configured_index:
            return True
        if device.name.lower() == configured_lower:
            return True
    return False


def _check_dcs_bios_reference(configured_dir: Path | None) -> CheckResult:
    reference_dirs = find_reference_dirs(configured_dir)
    if reference_dirs:
        return CheckResult("DCS-BIOS reference", "OK", str(reference_dirs[0]))
    return CheckResult(
        "DCS-BIOS reference",
        "WARN",
        "No DCS-BIOS reference JSON folder was found.",
        "Install DCS-BIOS or run setup and point to Saved Games\\DCS...\\Scripts\\DCS-BIOS\\doc\\json.",
    )


def _check_dcs_bios_export(saved_games_path: Path | None) -> CheckResult:
    status = inspect_dcs_bios_setup(saved_games_path)
    if status.export_lua_exists and status.export_lua_mentions_dcs_bios:
        return CheckResult("DCS-BIOS Export.lua", "OK", str(status.export_lua_file))
    if not status.export_lua_exists:
        return CheckResult(
            "DCS-BIOS Export.lua",
            "WARN",
            f"Missing: {status.export_lua_file}",
            "Run DCS-AI-Copilot.exe --dcs-bios-help for exact install steps.",
        )
    return CheckResult(
        "DCS-BIOS Export.lua",
        "WARN",
        f"Export.lua exists but does not load DCS-BIOS: {status.export_lua_file}",
        "Add the DCS-BIOS dofile line shown by DCS-AI-Copilot.exe --dcs-bios-help.",
    )


def _check_python_packages() -> list[CheckResult]:
    package_names = ["openai", "sounddevice", "pynput", "pygame", "google.genai"]
    results: list[CheckResult] = []
    for package_name in package_names:
        if importlib.util.find_spec(package_name) is not None:
            results.append(CheckResult(f"Python package {package_name}", "OK", "Installed."))
        else:
            results.append(
                CheckResult(
                    f"Python package {package_name}",
                    "FAIL",
                    "Not installed.",
                    "Run: python -m pip install -r requirements.txt",
                )
            )
    return results


def _check_openkneeboard() -> list[CheckResult]:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "OpenKneeboard" / "OpenKneeboard.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "OpenKneeboard" / "OpenKneeboard.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "OpenKneeboard" / "OpenKneeboard.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return [CheckResult("OpenKneeboard", "OK", str(candidate))]
    return [
        CheckResult(
            "OpenKneeboard",
            "WARN",
            "OpenKneeboard executable was not found in common install paths.",
            f"Install OpenKneeboard and add a Web Dashboard using {DEFAULT_WEB_URL}.",
        )
    ]


def _check_dashboard_port(host: str, port: int) -> list[CheckResult]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        result = sock.connect_ex((host, port))
    if result == 0:
        return [
            CheckResult(
                "Dashboard port",
                "WARN",
                f"{host}:{port} is already in use.",
                "If AI Copilot is already running this is fine. Otherwise stop the old process.",
            )
        ]
    return [CheckResult("Dashboard port", "OK", f"{host}:{port} is available.")]
