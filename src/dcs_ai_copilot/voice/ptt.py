from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from dcs_ai_copilot.kneeboard.renderer import render_kneeboard
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.audio import AudioClip, MicrophoneRecorder
from dcs_ai_copilot.voice.joystick import (
    JoystickPttListener,
    WinmmJoystickPttListener,
    list_winmm_joystick_devices,
    normalize_joystick_button,
)
from dcs_ai_copilot.voice.notes import parse_voice_note
from dcs_ai_copilot.voice.parser import CoordinateParseError, parse_coordinate_message
from dcs_ai_copilot.voice.transcriber import (
    TranscriptionResult,
    create_transcriber,
    friendly_transcription_error,
)


class Recorder(Protocol):
    def start(self) -> None: ...
    def stop(self) -> AudioClip: ...


class Transcriber(Protocol):
    @property
    def model(self) -> str: ...
    def transcribe(self, clip: AudioClip) -> TranscriptionResult: ...


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool
    ptt_mode: str
    keyboard_ptt_key: str
    joystick_backend: str
    joystick_name: str
    joystick_button: str
    joystick_winmm_device_id: str
    joystick_poll_interval_seconds: float
    input_device: str
    sample_rate: int
    channels: int
    max_record_seconds: float
    transcription_provider: str
    transcription_fallback_provider: str
    transcription_model: str
    gemini_transcription_model: str


class KeyMatcher:
    def __init__(self, key_name: str) -> None:
        self._key_name = key_name.lower().strip()

    def matches(self, key: object) -> bool:
        text = str(key).lower().strip("'")
        return text == self._key_name or text == f"key.{self._key_name}"


class PushToTalkService:
    def __init__(
        self,
        config: VoiceConfig,
        state: KneeboardState,
        kneeboard_file,
        logger: logging.Logger,
        recorder: Recorder | None = None,
        transcriber: Transcriber | None = None,
        listener_factory: Callable[..., object] | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._kneeboard_file = kneeboard_file
        self._logger = logger
        self._recorder = recorder or MicrophoneRecorder(
            sample_rate=config.sample_rate,
            channels=config.channels,
            input_device=config.input_device,
        )
        self._transcriber = transcriber or create_transcriber(
            provider=config.transcription_provider,
            fallback_provider=config.transcription_fallback_provider,
            openai_model=config.transcription_model,
            gemini_model=config.gemini_transcription_model,
        )
        self._listener_factory = listener_factory
        self._matcher = KeyMatcher(config.keyboard_ptt_key)
        self._lock = threading.Lock()
        self._recording = False
        self._ptt_down = False
        self._timer: threading.Timer | None = None
        self._keyboard_listener = None
        self._joystick_listener: JoystickPttListener | WinmmJoystickPttListener | None = None

    def start(self) -> None:
        joystick_button = normalize_joystick_button(self._config.joystick_button)
        self._state.update_voice(
            enabled=self._config.enabled,
            status="IDLE" if self._config.enabled else "DISABLED",
            is_recording=False,
            last_error="",
            ptt_key=self._config.keyboard_ptt_key.upper(),
            ptt_mode=self._config.ptt_mode.upper(),
            ptt_source="",
            joystick_backend=self._config.joystick_backend.upper(),
            joystick_name=self._config.joystick_name,
            joystick_button=joystick_button,
            joystick_status="DISABLED",
            joystick_detail="",
            model=self._transcriber.model,
        )
        if not self._config.enabled:
            return

        ptt_mode = self._config.ptt_mode.lower().strip()
        if ptt_mode in {"keyboard", "both", "joystick"}:
            self._start_keyboard_listener()
        if ptt_mode in {"joystick", "both"}:
            self._start_joystick_listener()

    def stop(self) -> None:
        self._cancel_timer()
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        if self._joystick_listener is not None:
            self._joystick_listener.stop()
        with self._lock:
            should_stop = self._recording
            self._recording = False
            self._ptt_down = False
        if should_stop:
            try:
                self._recorder.stop()
            except Exception as exc:
                self._logger.warning("Error stopping microphone recorder: %s", exc)
        self._state.update_voice(is_recording=False, status="STOPPED")

    def on_press(self, key: object) -> None:
        if not self._config.enabled or not self._matcher.matches(key):
            return
        self.begin_recording("KEYBOARD")

    def on_release(self, key: object) -> None:
        if not self._config.enabled or not self._matcher.matches(key):
            return
        self.finish_recording(reason="PTT RELEASED")

    def begin_recording(self, source: str) -> None:
        with self._lock:
            if self._recording or self._ptt_down:
                return
            self._recording = True
            self._ptt_down = True

        try:
            self._recorder.start()
        except Exception as exc:
            with self._lock:
                self._recording = False
                self._ptt_down = False
            self._state.update_voice(
                status="MIC ERROR",
                is_recording=False,
                last_error=str(exc),
            )
            self._logger.warning("Could not start microphone recording: %s", exc)
            return

        self._state.update_voice(
            status="RECORDING",
            is_recording=True,
            ptt_source=source,
            last_error="",
        )
        self._timer = threading.Timer(
            self._config.max_record_seconds,
            self._on_recording_timeout,
        )
        self._timer.daemon = True
        self._timer.start()

    def _on_recording_timeout(self) -> None:
        self.finish_recording(reason="MAX RECORDING TIME")

    def finish_recording(self, reason: str) -> None:
        with self._lock:
            if not self._recording:
                self._ptt_down = False
                return
            self._recording = False
            self._ptt_down = False

        self._cancel_timer()
        try:
            clip = self._recorder.stop()
        except Exception as exc:
            self._state.update_voice(
                status="MIC ERROR",
                is_recording=False,
                last_error=str(exc),
            )
            self._logger.warning("Could not stop microphone recording: %s", exc)
            return

        self._state.update_voice(status=reason, is_recording=False, ptt_source="")
        worker = threading.Thread(
            target=self._transcribe_and_parse,
            args=(clip,),
            name="voice-transcription-worker",
            daemon=True,
        )
        worker.start()

    def _transcribe_and_parse(self, clip: AudioClip) -> None:
        self._state.update_voice(status="TRANSCRIBING", is_recording=False)
        try:
            result = self._transcriber.transcribe(clip)
        except Exception as exc:
            friendly_error = friendly_transcription_error(exc)
            self._state.update_voice(
                status="TRANSCRIBE ERROR",
                is_recording=False,
                last_error=friendly_error,
            )
            self._logger.warning("Transcription failed: %s", friendly_error)
            return

        self._state.update_voice(
            status="TRANSCRIBED",
            last_transcript=result.text,
            last_error="",
        )
        note_text = parse_voice_note(result.text)
        if note_text is not None:
            try:
                snapshot = self._state.add_note(note_text)
                self._render_snapshot(snapshot)
            except Exception as exc:
                self._state.update_voice(
                    status="NOTE ERROR",
                    last_error=str(exc),
                )
                self._logger.warning("Could not save voice note: %s", exc)
                return

            self._state.update_voice(status="NOTE SAVED", last_error="")
            return

        try:
            capture = parse_coordinate_message(
                result.text,
                index=self._state.next_index(),
            )
        except CoordinateParseError as exc:
            self._state.update_voice(status="PARSE FAILED", last_error=str(exc))
            self._logger.info(
                "Transcript did not parse as coordinate: %s; transcript=%r",
                exc,
                result.text,
            )
            return

        snapshot = self._state.add_capture(capture)
        try:
            self._render_snapshot(snapshot)
        except Exception as exc:
            self._state.update_voice(
                status="RENDER ERROR",
                last_error=str(exc),
            )
            self._logger.warning("Could not render kneeboard data: %s", exc)
            return
        self._state.update_voice(status="PARSED", last_error="")

    def _render_snapshot(self, snapshot) -> None:
        render_kneeboard(
            snapshot.captures,
            self._kneeboard_file,
            notes=snapshot.notes,
        )

    def _cancel_timer(self) -> None:
        timer = self._timer
        self._timer = None
        if timer is not None:
            timer.cancel()

    def _start_keyboard_listener(self) -> None:
        listener_factory = self._listener_factory
        if listener_factory is None:
            from pynput import keyboard

            listener_factory = keyboard.Listener
        self._keyboard_listener = listener_factory(
            on_press=self.on_press,
            on_release=self.on_release,
        )
        self._keyboard_listener.start()

    def _start_joystick_listener(self) -> None:
        listener_class = self._select_joystick_listener()
        if listener_class is WinmmJoystickPttListener:
            self._joystick_listener = listener_class(
                device_name=self._config.joystick_name,
                device_id=self._config.joystick_winmm_device_id,
                button=self._config.joystick_button,
                on_press=lambda: self.begin_recording("JOYSTICK"),
                on_release=lambda: self.finish_recording("PTT RELEASED"),
                on_status=self._update_joystick_status,
                poll_interval_seconds=self._config.joystick_poll_interval_seconds,
            )
        else:
            self._joystick_listener = listener_class(
                device_name=self._config.joystick_name,
                button=self._config.joystick_button,
                on_press=lambda: self.begin_recording("JOYSTICK"),
                on_release=lambda: self.finish_recording("PTT RELEASED"),
                on_status=self._update_joystick_status,
                poll_interval_seconds=self._config.joystick_poll_interval_seconds,
            )
        self._joystick_listener.start()

    def _select_joystick_listener(self):
        backend = self._config.joystick_backend.lower().strip()
        if backend == "winmm":
            return WinmmJoystickPttListener
        if backend == "pygame":
            return JoystickPttListener
        if backend != "auto":
            self._update_joystick_status(
                "JOYSTICK ERROR",
                f"Unsupported joystick_backend: {self._config.joystick_backend}",
            )
            return JoystickPttListener

        device_name = self._config.joystick_name.lower()
        wants_takeoff_panel = "takeoff panel" in device_name or "f18 takeoff" in device_name
        if wants_takeoff_panel and list_winmm_joystick_devices():
            return WinmmJoystickPttListener
        return JoystickPttListener

    def _update_joystick_status(self, status: str, detail: str) -> None:
        self._state.update_voice(
            joystick_status=status,
            joystick_detail=detail,
            last_error="" if status == "JOYSTICK READY" else detail,
        )
