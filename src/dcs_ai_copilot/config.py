from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    kneeboard_file: Path
    log_file: Path
    web_host: str
    web_port: int
    dcs_install_path: Path | None
    dcs_saved_games_path: Path | None
    vr_platform: str
    vr_managed_by_ai_copilot: bool
    dcs_bios_enabled: bool
    dcs_bios_multicast_group: str
    dcs_bios_port: int
    dcs_bios_reference_dir: Path | None
    voice_enabled: bool
    voice_ptt_mode: str
    voice_keyboard_ptt_key: str
    voice_joystick_backend: str
    voice_joystick_name: str
    voice_joystick_button: str
    voice_joystick_winmm_device_id: str
    voice_joystick_poll_interval_seconds: float
    voice_input_device: str
    voice_sample_rate: int
    voice_channels: int
    voice_max_record_seconds: float
    voice_transcription_provider: str
    voice_transcription_fallback_provider: str
    voice_transcription_model: str
    voice_gemini_transcription_model: str
    buy_me_a_coffee_url: str
    env_file: Path


def load_config(config_file: Path) -> AppConfig:
    project_root = config_file.resolve().parent
    parser = configparser.ConfigParser()
    parser.read(config_file, encoding="utf-8")

    kneeboard_file = _resolve_path(
        project_root,
        parser.get("paths", "kneeboard_file", fallback="kneeboard.html"),
    )
    log_file = _resolve_path(
        project_root,
        parser.get("paths", "log_file", fallback="logs/dcs-ai-copilot.log"),
    )
    web_host = parser.get("web", "host", fallback="127.0.0.1")
    web_port = parser.getint("web", "port", fallback=8765)
    dcs_install_path = parser.get("dcs", "install_path", fallback="").strip()
    dcs_saved_games_path = parser.get("dcs", "saved_games_path", fallback="").strip()
    dcs_bios_reference = parser.get("dcs_bios", "reference_dir", fallback="").strip()
    env_file = _resolve_path(
        project_root,
        parser.get("voice", "env_file", fallback=".env"),
    )

    return AppConfig(
        project_root=project_root,
        kneeboard_file=kneeboard_file,
        log_file=log_file,
        web_host=web_host,
        web_port=web_port,
        dcs_install_path=(
            _resolve_path(project_root, dcs_install_path)
            if dcs_install_path
            else None
        ),
        dcs_saved_games_path=(
            _resolve_path(project_root, dcs_saved_games_path)
            if dcs_saved_games_path
            else None
        ),
        vr_platform=parser.get("vr", "platform", fallback="openxr-other").strip(),
        vr_managed_by_ai_copilot=parser.getboolean(
            "vr",
            "managed_by_ai_copilot",
            fallback=False,
        ),
        dcs_bios_enabled=parser.getboolean("dcs_bios", "enabled", fallback=True),
        dcs_bios_multicast_group=parser.get(
            "dcs_bios",
            "multicast_group",
            fallback="239.255.50.10",
        ),
        dcs_bios_port=parser.getint("dcs_bios", "port", fallback=5010),
        dcs_bios_reference_dir=(
            _resolve_path(project_root, dcs_bios_reference)
            if dcs_bios_reference
            else None
        ),
        voice_enabled=parser.getboolean("voice", "enabled", fallback=True),
        voice_ptt_mode=parser.get("voice", "ptt_mode", fallback="joystick"),
        voice_keyboard_ptt_key=parser.get(
            "voice",
            "keyboard_ptt_key",
            fallback=parser.get("voice", "ptt_key", fallback="f13"),
        ),
        voice_joystick_backend=parser.get("voice", "joystick_backend", fallback="auto"),
        voice_joystick_name=parser.get(
            "voice",
            "joystick_name",
            fallback="WINWING F/A-18 Takeoff Panel",
        ),
        voice_joystick_button=parser.get("voice", "joystick_button", fallback="0"),
        voice_joystick_winmm_device_id=parser.get(
            "voice",
            "joystick_winmm_device_id",
            fallback="auto",
        ),
        voice_joystick_poll_interval_seconds=parser.getfloat(
            "voice",
            "joystick_poll_interval_seconds",
            fallback=0.01,
        ),
        voice_input_device=parser.get("voice", "input_device", fallback="").strip(),
        voice_sample_rate=parser.getint("voice", "sample_rate", fallback=16000),
        voice_channels=parser.getint("voice", "channels", fallback=1),
        voice_max_record_seconds=parser.getfloat(
            "voice",
            "max_record_seconds",
            fallback=90.0,
        ),
        voice_transcription_provider=parser.get(
            "voice",
            "transcription_provider",
            fallback="openai",
        ).strip(),
        voice_transcription_fallback_provider=parser.get(
            "voice",
            "transcription_fallback_provider",
            fallback="",
        ).strip(),
        voice_transcription_model=parser.get(
            "voice",
            "transcription_model",
            fallback="gpt-4o-mini-transcribe",
        ).strip(),
        voice_gemini_transcription_model=parser.get(
            "voice",
            "gemini_transcription_model",
            fallback="gemini-2.5-flash",
        ).strip(),
        buy_me_a_coffee_url=parser.get(
            "donation",
            "buy_me_a_coffee_url",
            fallback="",
        ).strip(),
        env_file=env_file,
    )


def _resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    return project_root / path
