from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.logging_setup import configure_logging
from dcs_ai_copilot.voice.audio import AudioClip
from dcs_ai_copilot.voice.joystick import (
    WinmmJoystickDeviceInfo,
    WinmmJoystickPttListener,
    is_winmm_button_pressed,
    normalize_joystick_button,
)
from dcs_ai_copilot.voice.notes import parse_voice_note
from dcs_ai_copilot.voice.ptt import KeyMatcher, PushToTalkService, VoiceConfig
from dcs_ai_copilot.voice.transcriber import (
    TranscriptionResult,
    friendly_transcription_error,
)


class FakeRecorder:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def stop(self) -> AudioClip:
        self.stop_calls += 1
        return AudioClip(wav_bytes=b"RIFF....WAVE", sample_rate=16000, channels=1)


class FakeTranscriber:
    model = "gpt-4o-mini-transcribe"

    def __init__(self, text: str) -> None:
        self._text = text

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        return TranscriptionResult(text=self._text, model=self.model)


class SequenceTranscriber:
    model = "gpt-4o-mini-transcribe"

    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        text = self._texts[self.calls]
        self.calls += 1
        return TranscriptionResult(text=text, model=self.model)


class VoicePttTests(unittest.TestCase):
    def test_key_matcher_accepts_f13(self) -> None:
        matcher = KeyMatcher("f13")

        self.assertTrue(matcher.matches("Key.f13"))
        self.assertTrue(matcher.matches("f13"))
        self.assertFalse(matcher.matches("Key.f12"))

    def test_joy_btn1_maps_to_zero_based_button(self) -> None:
        self.assertEqual(normalize_joystick_button("JOY_BTN1"), 0)
        self.assertEqual(normalize_joystick_button("BTN_1"), 0)
        self.assertEqual(normalize_joystick_button("0"), 0)

    def test_winmm_button_mask_uses_zero_based_buttons(self) -> None:
        self.assertTrue(is_winmm_button_pressed(0x00000001, "JOY_BTN1"))
        self.assertTrue(is_winmm_button_pressed(0x00000002, "JOY_BTN2"))
        self.assertFalse(is_winmm_button_pressed(0x00000002, "JOY_BTN1"))

    def test_openai_quota_error_gets_friendly_message(self) -> None:
        message = friendly_transcription_error(
            RuntimeError("Error code: 429 - insufficient_quota")
        )

        self.assertIn("quota/billing", message)

    def test_note_prefix_extracts_freeform_text(self) -> None:
        self.assertEqual(parse_voice_note("note tanker 251 decimal 000"), "tanker 251 decimal 000")
        self.assertEqual(parse_voice_note("Notera fuel 4200"), "fuel 4200")
        self.assertEqual(parse_voice_note("anteckna fuel 4200"), "fuel 4200")
        self.assertIsNone(parse_voice_note("target north 42 15"))

    def test_winmm_takeoff_panel_can_be_selected_by_zero_axis_shape(self) -> None:
        listener = WinmmJoystickPttListener(
            device_name="WINWING F18 TAKEOFF PANEL 2",
            device_id="auto",
            button="JOY_BTN1",
            on_press=lambda: None,
            on_release=lambda: None,
            on_status=lambda status, detail: None,
        )
        listener._find_device = lambda: None
        devices = [
            WinmmJoystickDeviceInfo(1, "MS-drivrutin för PC-spelenhet", 6, 32, 32, 0),
            WinmmJoystickDeviceInfo(4, "MS-drivrutin för PC-spelenhet", 0, 32, 32, 0),
        ]

        selected = listener._select_from_devices(devices)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.device_id, 4)

    def test_recording_stops_when_f13_is_released(self) -> None:
        recorder = FakeRecorder()
        service = _build_service(recorder=recorder)

        service.on_press("Key.f13")
        service.on_release("Key.f13")

        self.assertEqual(recorder.start_calls, 1)
        self.assertEqual(recorder.stop_calls, 1)

    def test_transcript_is_parsed_into_coordinate_capture(self) -> None:
        state = KneeboardState()
        service = _build_service(
            state=state,
            transcriber=FakeTranscriber(
                "target north 42 15.732 east 041 38.219 elevation 428"
            ),
        )

        service.on_press("Key.f13")
        service.on_release("Key.f13")

        snapshot = _wait_for_voice_status(state, "PARSED")
        self.assertEqual(snapshot.voice["last_transcript"], "target north 42 15.732 east 041 38.219 elevation 428")
        self.assertEqual(snapshot.voice["status"], "PARSED")
        self.assertEqual(snapshot.captures[0].format_latitude(), "N42°15.732'")
        self.assertEqual(snapshot.captures[0].format_longitude(), "E041°38.219'")

    def test_note_transcript_is_saved_without_coordinate_parse(self) -> None:
        state = KneeboardState()
        service = _build_service(
            state=state,
            transcriber=FakeTranscriber("note tanker tacan 12 x fuel 4200"),
        )

        service.on_press("Key.f13")
        service.on_release("Key.f13")

        snapshot = _wait_for_voice_status(state, "NOTE SAVED")
        self.assertEqual(snapshot.voice["status"], "NOTE SAVED")
        self.assertEqual(snapshot.notes[0].text, "tanker tacan 12 x fuel 4200")
        self.assertEqual(snapshot.captures, [])

    def test_ptt_still_records_after_twenty_notes(self) -> None:
        state = KneeboardState()
        recorder = FakeRecorder()
        transcriber = SequenceTranscriber(
            [f"note test note {index}" for index in range(1, 22)]
        )
        service = _build_service(
            state=state,
            recorder=recorder,
            transcriber=transcriber,
        )

        for index in range(1, 21):
            service.on_press("Key.f13")
            service.on_release("Key.f13")
            snapshot = _wait_for_note_count(state, index)
            self.assertEqual(snapshot.voice["status"], "NOTE SAVED")

        self.assertEqual(recorder.start_calls, 20)
        self.assertEqual(recorder.stop_calls, 20)
        self.assertEqual(len(state.snapshot().notes), 20)

        service.on_press("Key.f13")
        self.assertEqual(recorder.start_calls, 21)
        self.assertTrue(state.snapshot().voice["is_recording"])
        service.on_release("Key.f13")
        snapshot = _wait_for_note_count(state, 21)

        self.assertEqual(recorder.stop_calls, 21)
        self.assertEqual(snapshot.voice["status"], "NOTE SAVED")
        self.assertEqual(len(snapshot.notes), 21)


def _build_service(
    state: KneeboardState | None = None,
    recorder: FakeRecorder | None = None,
    transcriber: FakeTranscriber | None = None,
) -> PushToTalkService:
    logger = configure_logging(ROOT / "logs" / "test-voice.log")
    return PushToTalkService(
        VoiceConfig(
            enabled=True,
            ptt_mode="joystick",
            keyboard_ptt_key="f13",
            joystick_backend="auto",
            joystick_name="WINWING F/A-18 Takeoff Panel",
            joystick_button="JOY_BTN1",
            joystick_winmm_device_id="auto",
            joystick_poll_interval_seconds=0.01,
            sample_rate=16000,
            channels=1,
            input_device="",
            max_record_seconds=20,
            transcription_provider="openai",
            transcription_fallback_provider="gemini",
            transcription_model="gpt-4o-mini-transcribe",
            gemini_transcription_model="gemini-2.5-flash",
        ),
        state or KneeboardState(),
        ROOT / ".runtime" / "kneeboard-test.html",
        logger,
        recorder=recorder or FakeRecorder(),
        transcriber=transcriber
        or FakeTranscriber("target north 42 15.732 east 041 38.219 elevation 428"),
    )


def _wait_for_voice_status(state: KneeboardState, status: str):
    deadline = time.time() + 2
    while time.time() < deadline:
        snapshot = state.snapshot()
        if snapshot.voice["status"] == status:
            return snapshot
        time.sleep(0.01)
    raise AssertionError(f"voice status did not become {status}")


def _wait_for_note_count(state: KneeboardState, count: int):
    deadline = time.time() + 2
    while time.time() < deadline:
        snapshot = state.snapshot()
        if len(snapshot.notes) >= count and snapshot.voice["status"] == "NOTE SAVED":
            return snapshot
        time.sleep(0.01)
    raise AssertionError(f"note count did not become {count}")


if __name__ == "__main__":
    unittest.main()
