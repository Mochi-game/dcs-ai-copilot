from __future__ import annotations

import logging
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, replace
from typing import Callable, Protocol

from dcs_ai_copilot.kneeboard.renderer import render_kneeboard
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.audio import AudioClip, MicrophoneRecorder, microphone_choices
from dcs_ai_copilot.voice.joystick import (
    JoystickPttListener,
    WinmmJoystickPttListener,
    list_winmm_joystick_devices,
    normalize_joystick_button,
)
from dcs_ai_copilot.voice.router import apply_case3_command, normalize_command, parse_command
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
    MAX_PENDING_CLIPS = 8

    def __init__(
        self,
        config: VoiceConfig,
        state: KneeboardState,
        kneeboard_file,
        logger: logging.Logger,
        recorder: Recorder | None = None,
        transcriber: Transcriber | None = None,
        listener_factory: Callable[..., object] | None = None,
        save_input_device: Callable[[str], None] | None = None,
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
        self._save_input_device = save_input_device
        self._matcher = KeyMatcher(config.keyboard_ptt_key)
        self._lock = threading.RLock()
        self._apply_lock = threading.Lock()
        self._pending: deque[AudioClip] = deque()
        self._worker: threading.Thread | None = None
        self._processing = False
        self._stopped = False
        self._active_source = ""
        self._recording_id = 0
        self._recording = False
        self._ptt_down = False
        self._timer: threading.Timer | None = None
        self._keyboard_listener = None
        self._joystick_listener: JoystickPttListener | WinmmJoystickPttListener | None = None

    def start(self) -> None:
        joystick_button = normalize_joystick_button(self._config.joystick_button)
        self._update_voice(
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
            selected_input=self._config.input_device,
        )
        if not self._config.enabled:
            return

        describe_input = getattr(self._recorder, "describe_input", None)
        if describe_input is not None:
            try:
                self._update_voice(input_device=describe_input())
            except Exception as exc:
                self._update_voice(input_device="UNAVAILABLE", last_error=str(exc))
                self._logger.warning("Could not inspect microphone: %s", exc)

        ptt_mode = self._config.ptt_mode.lower().strip()
        if ptt_mode in {"keyboard", "both", "joystick"}:
            self._start_keyboard_listener()
        if ptt_mode in {"joystick", "both"}:
            self._start_joystick_listener()

    def list_microphones(self) -> dict[str, object]:
        devices = microphone_choices()
        with self._lock:
            return {"devices": devices, "selected": self._config.input_device}

    def select_microphone(self, device: str) -> None:
        def require_idle() -> None:
            if self._stopped:
                raise RuntimeError("Voice service is stopped.")
            if self._recording or self._ptt_down:
                raise RuntimeError("Release PTT before changing microphone.")

        try:
            with self._lock:
                require_idle()
            if device not in {item["value"] for item in microphone_choices()}:
                raise ValueError("Microphone not found. Refresh the device list.")
            candidate = MicrophoneRecorder(
                sample_rate=self._config.sample_rate,
                channels=self._config.channels, input_device=device,
            )
            candidate.validate_input()
            description = candidate.describe_input()
            # Device inspection may take time; recheck PTT before committing.
            with self._lock:
                require_idle()
                if self._save_input_device is not None:
                    self._save_input_device(device)
                self._recorder = candidate
                self._config = replace(self._config, input_device=device)
                self._update_voice(
                    input_device=description, selected_input=device, last_error="",
                )
        except Exception as exc:
            self._update_voice(last_error=f"Microphone selection failed: {exc}")
            raise

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            self._cancel_timer()
            self._pending.clear()
            if self._recording:
                try:
                    self._recorder.stop()
                except Exception as exc:
                    self._logger.warning("Error stopping microphone recorder: %s", exc)
            self._recording = False
            self._ptt_down = False
            self._active_source = ""
            self._state.update_voice(
                is_recording=False, status="STOPPED", ptt_source="", pending_count=0,
            )
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        if self._joystick_listener is not None:
            self._joystick_listener.stop()
        # Let an already-applying result finish before stop returns, without
        # blocking microphone release on routing or HTML file writes.
        with self._apply_lock:
            pass

    def on_press(self, key: object) -> None:
        if not self._config.enabled or not self._matcher.matches(key):
            return
        self.begin_recording("KEYBOARD")

    def on_release(self, key: object) -> None:
        if not self._config.enabled or not self._matcher.matches(key):
            return
        self.finish_recording(reason="PTT RELEASED", source="KEYBOARD")

    def begin_recording(self, source: str) -> None:
        # Serialize microphone open/close so a rapid release cannot leave it open.
        with self._lock:
            if self._stopped or not self._config.enabled or self._recording or self._ptt_down:
                return
            if len(self._pending) >= self.MAX_PENDING_CLIPS:
                self._update_voice(
                    status="VOICE BUSY",
                    last_error="Transcription queue is full. Wait for pending notes, then press PTT again.",
                )
                return
            self._active_source = source
            self._ptt_down = True
            try:
                self._recorder.start()
            except Exception as exc:
                self._ptt_down = False
                self._active_source = ""
                self._update_voice(status="MIC ERROR", last_error=str(exc))
                self._logger.warning("Could not start microphone recording: %s", exc)
                return

            self._recording = True
            self._recording_id += 1
            self._update_voice(status="RECORDING", last_error="")
            self._timer = threading.Timer(
                self._config.max_record_seconds,
                self._on_recording_timeout,
                args=(self._recording_id,),
            )
            self._timer.daemon = True
            self._timer.start()

    def _on_recording_timeout(self, recording_id: int | None = None) -> None:
        self.finish_recording(reason="MAX RECORDING TIME", recording_id=recording_id)

    def finish_recording(
        self, reason: str, source: str | None = None, recording_id: int | None = None,
    ) -> None:
        with self._lock:
            if self._stopped:
                return
            if source is not None and source != self._active_source:
                return
            if recording_id is not None and recording_id != self._recording_id:
                return
            timed_out = reason == "MAX RECORDING TIME"
            if not timed_out:
                self._ptt_down = False
                self._active_source = ""
            if not self._recording:
                return
            self._recording = False
            self._cancel_timer()
            try:
                clip = self._recorder.stop()
            except Exception as exc:
                self._update_voice(status="MIC ERROR", last_error=str(exc))
                self._logger.warning("Could not stop microphone recording: %s", exc)
                return

            self._pending.append(clip)
            self._update_voice(status=reason)
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._process_pending,
                    name="voice-transcription-worker",
                    daemon=True,
                )
                self._worker.start()

    def _process_pending(self) -> None:
        # One FIFO worker preserves spoken note/clear/CASE III command order.
        # It exits when idle instead of leaving one waiting thread per service.
        while True:
            with self._lock:
                if self._stopped or not self._pending:
                    self._worker = None
                    self._processing = False
                    self._update_voice()
                    return
                clip = self._pending.popleft()
                self._processing = True
            try:
                self._transcribe_and_parse(clip)
            except Exception as exc:
                self._logger.exception("Voice worker recovered from an unexpected error")
                self._update_voice(status="VOICE ERROR", last_error=str(exc))
            finally:
                with self._lock:
                    self._processing = False
                    self._update_voice()

    def _update_voice(self, **updates: object) -> None:
        with self._lock:
            if self._stopped:
                return
            updates["is_recording"] = self._recording
            updates["ptt_source"] = self._active_source if self._recording else ""
            updates["pending_count"] = len(self._pending) + int(self._processing)
            if self._recording:
                updates["status"] = "RECORDING"
            self._state.update_voice(**updates)

    def _transcribe_and_parse(self, clip: AudioClip) -> None:
        self._update_voice(status="TRANSCRIBING", is_recording=False)
        started = time.perf_counter()
        try:
            result = self._transcriber.transcribe(clip)
        except Exception as exc:
            friendly_error = friendly_transcription_error(exc)
            self._update_voice(
                status="TRANSCRIBE ERROR",
                is_recording=False,
                last_error=friendly_error,
            )
            self._logger.warning("Transcription failed: %s", friendly_error)
            return

        elapsed = time.perf_counter() - started
        with self._apply_lock:
            if self._stopped:
                return
            self._update_voice(last_latency_seconds=round(elapsed, 2), last_model=result.model)
            self._apply_transcript(result, clip, elapsed)

    def _apply_transcript(self, result: TranscriptionResult, clip: AudioClip, elapsed: float) -> None:
        self._logger.info(
            "STT completed: model=%s audio=%.2fs processing=%.2fs",
            result.model, clip.duration_seconds, elapsed,
        )
        self._update_voice(
            status="TRANSCRIBED",
            last_transcript=result.text,
            last_error="",
        )
        command = parse_command(result.text, active_view=self._state.snapshot().app["active_view"])
        self._logger.info(
            "STT RAW: %s\nNORMALIZED: %s\nROUTED: %s",
            json.dumps(result.text, ensure_ascii=False),
            json.dumps(normalize_command(result.text), ensure_ascii=False),
            command.route_name,
        )
        try:
            handled = apply_case3_command(command, self._state)
        except ValueError as exc:
            self._update_voice(status="COMMAND ERROR", last_error=str(exc))
            return
        if handled:
            self._update_voice(status="READY", last_error="")
            return

        if command.kind == "clear_notes":
            try:
                snapshot = self._state.clear_notes()
                self._render_snapshot(snapshot)
            except Exception as exc:
                self._update_voice(
                    status="CLEAR NOTES ERROR",
                    last_error=str(exc),
                )
                self._logger.warning("Could not clear voice notes: %s", exc)
                return

            self._update_voice(status="NOTES CLEARED", last_error="")
            return

        note_text = command.value if command.kind == "note" else None
        if note_text is not None:
            try:
                snapshot = self._state.add_note(note_text)
                self._render_snapshot(snapshot)
            except Exception as exc:
                self._update_voice(
                    status="NOTE ERROR",
                    last_error=str(exc),
                )
                self._logger.warning("Could not save voice note: %s", exc)
                return

            self._update_voice(status="NOTE SAVED", last_error="")
            return

        try:
            capture = parse_coordinate_message(
                result.text,
                index=self._state.next_index(),
            )
        except CoordinateParseError as exc:
            self._update_voice(status="PARSE FAILED", last_error=str(exc))
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
            self._update_voice(
                status="RENDER ERROR",
                last_error=str(exc),
            )
            self._logger.warning("Could not render kneeboard data: %s", exc)
            return
        self._update_voice(status="PARSED", last_error="")

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
                on_release=lambda: self.finish_recording("PTT RELEASED", source="JOYSTICK"),
                on_status=self._update_joystick_status,
                poll_interval_seconds=self._config.joystick_poll_interval_seconds,
            )
        else:
            self._joystick_listener = listener_class(
                device_name=self._config.joystick_name,
                button=self._config.joystick_button,
                on_press=lambda: self.begin_recording("JOYSTICK"),
                on_release=lambda: self.finish_recording("PTT RELEASED", source="JOYSTICK"),
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
        updates = {"joystick_status": status, "joystick_detail": detail}
        if status != "JOYSTICK READY":
            updates["last_error"] = detail
        self._update_voice(**updates)
