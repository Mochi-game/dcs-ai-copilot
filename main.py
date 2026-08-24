from __future__ import annotations

import argparse
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if not getattr(sys, "frozen", False) and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dcs_ai_copilot.app_paths import ensure_config_root, runtime_root
from dcs_ai_copilot.config import load_config
from dcs_ai_copilot.dcs_bios.reader import DcsBiosReader, DcsBiosReaderConfig
from dcs_ai_copilot.env import load_env_file
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.kneeboard.renderer import render_kneeboard
from dcs_ai_copilot.logging_setup import configure_logging
from dcs_ai_copilot.setup.maintenance import (
    backup_dcs_saved_games,
    default_dcs_saved_games_path,
    format_release_check_report,
    license_help,
    release_check_exit_code,
    run_release_check,
    uninstall_help,
)
from dcs_ai_copilot.setup.doctor import format_doctor_report, run_doctor
from dcs_ai_copilot.setup.dcs_bios_help import format_dcs_bios_setup_help, inspect_dcs_bios_setup
from dcs_ai_copilot.setup.wizard import run_setup_wizard, setup_help_text
from dcs_ai_copilot.voice.audio import run_audio_diagnostics
from dcs_ai_copilot.voice.parser import CoordinateParseError, parse_coordinate_message
from dcs_ai_copilot.voice.joystick import run_joystick_diagnostics
from dcs_ai_copilot.voice.ptt import PushToTalkService, VoiceConfig
from dcs_ai_copilot.web.server import start_kneeboard_server


def main() -> int:
    user_config_root = ensure_config_root()
    args = parse_args()
    app_root = runtime_root()
    if args.setup:
        return run_setup_wizard(user_config_root)
    if args.setup_help:
        print(setup_help_text())
        return 0
    if args.doctor:
        print(format_doctor_report(run_doctor(user_config_root / "config.ini")))
        return 0
    if args.dcs_bios_help:
        config_file = user_config_root / "config.ini"
        saved_games_path = None
        if config_file.exists():
            saved_games_path = load_config(config_file).dcs_saved_games_path
        print(format_dcs_bios_setup_help(inspect_dcs_bios_setup(saved_games_path)))
        return 0
    if args.backup_dcs:
        source = Path(args.dcs_saved_games) if args.dcs_saved_games else default_dcs_saved_games_path()
        backup_path = backup_dcs_saved_games(source, Path(args.backup_dcs))
        print(f"DCS Saved Games backup created: {backup_path}")
        return 0
    if args.uninstall_help:
        print(uninstall_help(app_root))
        return 0
    if args.license_help:
        release_project_root = (
            Path(args.release_project_root)
            if args.release_project_root
            else default_release_project_root(app_root)
        )
        print(license_help(release_project_root))
        return 0
    if args.release_check:
        release_project_root = (
            Path(args.release_project_root)
            if args.release_project_root
            else default_release_project_root(app_root)
        )
        results = run_release_check(release_project_root, version=args.release_version)
        print(format_release_check_report(results))
        return release_check_exit_code(results)
    if args.diagnose_joysticks:
        return run_joystick_diagnostics(include_axes=args.diagnose_joystick_axes)
    if args.diagnose_audio:
        return run_audio_diagnostics()

    config_file = user_config_root / "config.ini"
    if not config_file.exists():
        print("First-time setup is required.")
        print(f"Run: {Path(sys.argv[0]).name} --setup")
        print(f"Config folder: {user_config_root}")
        return 1

    config = load_config(config_file)
    load_env_file(config.env_file)
    logger = configure_logging(config.log_file)
    state = KneeboardState()
    state.update_app(buy_me_a_coffee_url=config.buy_me_a_coffee_url)

    try:
        server, thread = start_kneeboard_server(
            state,
            host=config.web_host,
            port=config.web_port,
        )
    except OSError as exc:
        logger.error("Could not start web dashboard: %s", exc)
        print(f"Could not start web dashboard on {config.web_host}:{config.web_port}.")
        print("Close any older dcs-ai-copilot/python instance using that port and try again.")
        return 1
    dcs_bios_reader = DcsBiosReader(
        DcsBiosReaderConfig(
            enabled=config.dcs_bios_enabled,
            multicast_group=config.dcs_bios_multicast_group,
            port=config.dcs_bios_port,
            reference_dir=config.dcs_bios_reference_dir,
        ),
        state,
        logger,
    )
    dcs_bios_reader.start()
    voice_service = PushToTalkService(
        VoiceConfig(
            enabled=config.voice_enabled,
            ptt_mode=config.voice_ptt_mode,
            keyboard_ptt_key=config.voice_keyboard_ptt_key,
            joystick_backend=config.voice_joystick_backend,
            joystick_name=config.voice_joystick_name,
            joystick_button=config.voice_joystick_button,
            joystick_winmm_device_id=config.voice_joystick_winmm_device_id,
            joystick_poll_interval_seconds=config.voice_joystick_poll_interval_seconds,
            input_device=config.voice_input_device,
            sample_rate=config.voice_sample_rate,
            channels=config.voice_channels,
            max_record_seconds=config.voice_max_record_seconds,
            transcription_provider=config.voice_transcription_provider,
            transcription_fallback_provider=config.voice_transcription_fallback_provider,
            transcription_model=config.voice_transcription_model,
            gemini_transcription_model=config.voice_gemini_transcription_model,
        ),
        state,
        config.kneeboard_file,
        logger,
    )
    try:
        voice_service.start()
    except Exception as exc:
        state.update_voice(
            enabled=False,
            status="VOICE ERROR",
            is_recording=False,
            last_error=str(exc),
            ptt_key=config.voice_keyboard_ptt_key.upper(),
            model=config.voice_transcription_model,
        )
        logger.warning("Voice service could not start: %s", exc)

    logger.info("DCS AI Copilot web dashboard started")
    print("DCS AI Copilot - OpenKneeboard Web Dashboard")
    print(f"URL: http://{config.web_host}:{config.web_port}")
    print(f"Voice PTT: {config.voice_ptt_mode.upper()}")
    print(f"Joystick backend: {config.voice_joystick_backend.upper()}")
    print(f"Joystick: {config.voice_joystick_name} button {config.voice_joystick_button}")
    print(f"WinMM device id: {config.voice_joystick_winmm_device_id}")
    print(f"Keyboard fallback: {config.voice_keyboard_ptt_key.upper()}")
    print(f"Microphone input: {config.voice_input_device or 'DEFAULT'}")
    print(f"Speech provider: {config.voice_transcription_provider.upper()}")
    print(f"Speech fallback: {config.voice_transcription_fallback_provider.upper() or 'OFF'}")
    print("Type coordinate messages, then press Enter.")
    print("Type 'quit' or press Ctrl+C to stop.")
    print('Example: target north 42 15.732 east 041 38.219 elevation 428')
    print()

    try:
        while True:
            try:
                raw_text = input("> ").strip()
            except EOFError:
                break
            if not raw_text:
                continue
            if raw_text.lower() in {"q", "quit", "exit"}:
                break

            try:
                capture = parse_coordinate_message(raw_text, index=state.next_index())
            except CoordinateParseError as exc:
                logger.warning("Could not parse coordinate input: %s", exc)
                print(f"Could not parse coordinate input: {exc}")
                continue

            snapshot = state.add_capture(capture)
            output_path = render_kneeboard(
                snapshot.captures,
                config.kneeboard_file,
                notes=snapshot.notes,
            )
            logger.info("Updated kneeboard data: %s", output_path)
            print(f"Captured {capture.kind.upper()} {capture.index}")
            print(capture.format_latitude())
            print(capture.format_longitude())
            print(capture.format_elevation())
            print()
    except KeyboardInterrupt:
        print()
        logger.info("Shutdown requested")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        dcs_bios_reader.stop()
        voice_service.stop()
        logger.info("DCS AI Copilot stopped")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DCS AI Copilot")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run first-time setup wizard and write config.ini/.env.",
    )
    parser.add_argument(
        "--setup-help",
        action="store_true",
        help="Print post-install setup help without changing config.ini or .env.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check config, dependencies, OpenKneeboard hints and dashboard port.",
    )
    parser.add_argument(
        "--dcs-bios-help",
        action="store_true",
        help="Print DCS-BIOS install/repair steps and local status without changing DCS files.",
    )
    parser.add_argument(
        "--backup-dcs",
        metavar="DESTINATION_DIR",
        help="Back up DCS Saved Games configuration to a destination folder.",
    )
    parser.add_argument(
        "--dcs-saved-games",
        metavar="SOURCE_DIR",
        help="Override DCS Saved Games source folder for --backup-dcs.",
    )
    parser.add_argument(
        "--uninstall-help",
        action="store_true",
        help="Print safe uninstall guidance for this development copy.",
    )
    parser.add_argument(
        "--license-help",
        action="store_true",
        help="Print license choices and steps required before public GitHub publishing.",
    )
    parser.add_argument(
        "--release-check",
        action="store_true",
        help="Check whether release artifacts are ready for public GitHub publishing.",
    )
    parser.add_argument(
        "--release-version",
        default="2.0",
        help="Release version to check with --release-check.",
    )
    parser.add_argument(
        "--release-project-root",
        help="Project root to check with --release-check. Defaults to the current app/source root.",
    )
    parser.add_argument(
        "--diagnose-joysticks",
        action="store_true",
        help="List joystick devices and print button down/up events.",
    )
    parser.add_argument(
        "--diagnose-joystick-axes",
        action="store_true",
        help="Also print joystick axis and hat movement during diagnostics.",
    )
    parser.add_argument(
        "--diagnose-audio",
        action="store_true",
        help="List microphone/input devices visible to sounddevice.",
    )
    return parser.parse_args()


def default_release_project_root(app_root: Path) -> Path:
    if app_root.parent.name.lower() == "dist" and (app_root.parent.parent / "release").exists():
        return app_root.parent.parent
    return app_root


if __name__ == "__main__":
    raise SystemExit(main())
